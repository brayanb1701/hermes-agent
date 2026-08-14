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
- Live executable checkout: `/home/brayan/.hermes/hermes-agent`
- Isolated CI worktree used by the pre-run script: `/home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci`
- Target branch: `brayan/personal-hermes-customizations`
- Fork origin: `git@github.com:brayanb1701/hermes-agent.git`
- Official upstream: `git@github.com:NousResearch/hermes-agent.git`
- Workflow doc: `~/personal_vault/_meta/workflows/hermes/hermes-fork-update-workflow.md`
- Pre-run wake-gate script: `~/.hermes/scripts/hermes_upstream_rebase_ci.py`
  - The scheduler runs this before the agent is created.
  - Normal rebases/tests happen in the isolated worktree, not in the live gateway checkout.
  - After a verified candidate is pushed, the script schedules a detached transient unit that runs `hermes update --branch brayan/personal-hermes-customizations --yes --no-backup`; this activates the candidate, refreshes dependencies/config, and restarts the gateway.
  - If the live checkout was moved to `main` by an older/raw update path, a clean checkout is recovered from `origin/brayan/personal-hermes-customizations` instead of failing preflight.
  - If it emits `wakeAgent: false`, no LLM agent runs.
  - If it emits `wakeAgent: true` or errors, its JSON/stdout is injected into the cron prompt for diagnosis.
  - Do not rerun it casually from the exception agent; inspect its injected output/current logs first. Rerun only when deliberately re-testing the whole pre-run automation after repairs.
- Cron job: `hermes-upstream-rebase-ci`, scheduled after morning startup (`30 9 * * *` as of 2026-04-30), delivery `local`, wake-gated by the script.

## Rules
1. First inspect the script JSON context and current git state.
2. Follow systematic debugging: identify the exact failure stage before fixing anything.
3. Preserve Brayan's source customizations. Do not run `git reset --hard upstream/main` unless there is a deliberate reason and the customization commit is safely recoverable.
4. Before changing Hermes base code, ask whether the improvement/fix can be done via plugin, config, skill, script, or vault workflow. Prefer those unless base-code change is genuinely required.
5. Resolve rebase conflicts or test failures if present. If the script reports the isolated worktree path, fix the worktree, not the live checkout.
6. Run focused verification from the script/doc.
7. If verification passes and branch is healthy, push only the personalization branch. For normal no-conflict script runs, `~/.hermes/scripts/hermes_upstream_rebase_ci.py` may push directly. For exception-agent/manual-repair runs, do **not** run direct terminal `git push --force-with-lease ...`; use the skill-owned finalizer script below. Never push personalization to `origin/main`.
8. Prefer programmatic recovery before manual edits: inspect the script output, let the script use `git rerere`/`rerere.autoupdate` and `GIT_EDITOR=true git rebase --continue` when conflicts have already been resolved, and only manually resolve genuinely new conflicts or failing tests.
9. If a conflict is manually resolved, make the resolution durable: keep repo-local `rerere.enabled=true` and `rerere.autoupdate=true`, continue the rebase, run verification, and update this skill/script/docs if the conflict suggests a reusable rule.
10. After a manual conflict resolution in the isolated worktree, do **not** move the live branch first. Finalize the repaired candidate directly with `scripts/finalize_rebase_push.py --repo /home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci --apply`. The finalizer is a narrow deterministic capability: hard-coded allowed repos, branch/remotes, exact force-with-lease, clean-tree checks, candidate-source tests/config check, remote verification, and detached live activation. If it refuses or fails, report its `stage`, `message`, failed command output, and `next_action`; do not bypass it with a direct force push.
11. After a successful script/finalizer run, verify both remote and activation surfaces: local/origin counts are `0 0` after activation, `upstream/main` is an ancestor of `HEAD`, the live worktree is clean, `hermes config check` is current, `hermes gateway status` is healthy, and the transient activation unit/journal reports success. If config migration changes live runtime config after activation, sync it into `brayan-personalization/runtime/`, commit only allowed snapshot paths, and finalize once more so the fork preserves the migrated config. Do not hand-edit `_config_version`.
12. Update the workflow doc or `_meta/log.md` only for meaningful workflow changes, conflict resolution notes, or persistent lessons.
13. Final response should be concise: failure stage, fix, tests/finalizer stage, current HEAD, push status, and manual action needed.

## Finalizer script for exception-agent repairs

When this exception agent has repaired a failed rebase, finalize the isolated candidate directly instead of moving the live checkout or calling `git push --force-with-lease` from the terminal tool:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/skills/automation-agents/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py \
  --repo /home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci \
  --apply
```

For diagnosis without pushing:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/skills/automation-agents/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py \
  --repo /home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci
```

For full verification without pushing:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python \
  /home/brayan/.hermes/skills/automation-agents/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py \
  --repo /home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci \
  --check
```

The finalizer emits JSON designed for agent use. On failure, inspect and report:
- `stage`
- `message`
- `next_action`
- failed entries in `commands`
- `checks` / `failed_check` when present

Do not bypass finalizer refusals. The finalizer intentionally hard-codes repo, branch, remotes, clean-tree checks, upstream containment, verification commands, and exact `--force-with-lease=<ref>:<observed-origin-sha>` push semantics.

## Known failure modes

- A detached activation launched from this cron exception handler can appear stuck after `✓ Update complete!` at `hermes-gateway: draining (...)`. This is expected while the current exception-agent turn is itself active in the gateway: graceful SIGUSR1 restart waits for that turn to finish, so waiting for the activation service to exit from inside the same turn creates a self-wait. Verify that the updater reached update completion, config migration/sync, the intended live HEAD, and gateway `active/running`; then stop only superseded duplicate activation units if a second finalization is required. For the final activation, report `activation_scheduled: true` and let the turn finish so the gateway can drain and restart. Do not force-restart the gateway from the active cron turn, and do not classify this expected drain wait as activation failure.
- The personalization snapshot must be deterministic. In particular, `scripts/sync-brayan-personalization.py` must drop cron `updated_at`, per-job `fire_claim`, channel-directory `updated_at`, and manifest generation timestamps, and must exclude skill runtime state such as `.usage.json` and `.curator_state`. A cron pre-run script executes while its own `fire_claim` is active; snapshotting that claim manufactures a commit, push, and live restart every tick. Verify repairs by running sync twice and comparing the resulting diff hash, then trigger one real cron run and confirm `status: up_to_date`, `activation_scheduled: false`, and no new commit.
- A failed rebase in the live checkout can break the already-running gateway without a clean restart. The scheduler/gateway process may have imported some modules before the rebase, then lazily import other modules after files changed, producing mixed old/new code errors such as `TypeError: ContextCompressor.__init__() got an unexpected keyword argument 'abort_on_summary_failure'`. A Telegram `/new` or new session will not help because the process/module state is wrong, not the conversation. The cron pre-run script is now hardened to perform rebases/tests in `/home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci` instead of mutating the live checkout. If the live checkout ever is mid-conflict, do **not** restart the gateway while conflict markers remain in source files; first resolve/abort the live rebase so `gateway/run.py` compiles, then restart and verify `hermes gateway status` plus recent logs. See `references/2026-05-live-checkout-rebase-poisoning.md` for the incident-specific diagnostic and verification pattern.
- If the script wakes at `stage: preflight` because live `brayan/personal-hermes-customizations` and `origin/brayan/personal-hermes-customizations` diverged, inspect live/origin/worktree ancestry and source-only diffs rather than choosing by recency. Repair and verify the isolated worktree candidate, then finalize it directly with `--repo /home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci --apply`; the finalizer pushes and schedules live activation. Do not move the live branch before candidate verification/remote publication. The historical references remain useful for ancestry/equivalence diagnosis, but their manual `git update-ref` activation steps are superseded by the detached updater.
- If the script wakes at `stage: fetch_upstream` with a transient DNS/network error, first confirm no rebase/worktree mutation started and that live/worktree are clean. Once DNS/fetch works again, deliberately rerun the pre-run script; a successful rerun now pushes and schedules live activation automatically. Inspect the activation unit/journal rather than manually moving the live ref.
- If the script wakes at `stage: preflight` because live and origin diverged but `git cherry -v origin/brayan/personal-hermes-customizations HEAD` shows every live-only commit as patch-equivalent (`-`), treat live as stale rather than richer. Use raw untruncated subprocess stdout for this check, choose origin as the isolated-worktree base, preserve backup refs, and after verification finalize the candidate directly from the isolated worktree so detached activation updates live. See `references/2026-06-live-stale-origin-patch-equivalent-repair.md` for historical diagnosis; its manual live-ref activation is superseded.
- If `git cherry` shows a live-only `+` commit, do not automatically treat live as richer. First compare likely origin equivalents by subject, `git show --stat`, and `git range-diff <live>^..<live> <origin>^..<origin>`. A commit can be non-patch-equivalent only because upstream context drift changed hunk anchors while the feature is already present on origin. If origin/worktree is the verified rebased candidate and live has no real unique content, preserve backup refs, sync/commit allowed personalization changes in the candidate, rebase onto `upstream/main`, and finalize the isolated candidate directly. Detached activation handles the live checkout. See `references/2026-06-live-origin-divergence-equivalent-feature.md` for historical diagnosis only.
- A concrete variant is the Telegram polling preservation fix: the old live patch touched `gateway/platforms/telegram.py`, while the rebased origin branch preserved the behavior in `plugins/platforms/telegram/adapter.py`, so `git cherry` reported a false live-only `+`. Treat origin as equivalent only after checking same-subject history plus behavior/test guards (`drop_pending_updates=False` and `test_polling_connect_preserves_pending_updates`) across both old/new paths. Prefer `git grep <ref> -- <candidate paths>` for this guard because `git show <ref>:<path>` fails when one candidate path does not exist. See `references/2026-06-telegram-polling-equivalent-origin.md`.
- If that divergence repair succeeds but the finalizer's `hermes_config_check` stdout reports `Config version: N → N+1`, treat the finalizer as only provisionally successful. Run `hermes config migrate`, sync the migrated runtime config into `brayan-personalization/runtime/`, commit only allowed snapshot paths, and rerun the skill-owned finalizer. If a temporary repair branch was used in the isolated worktree, detach the worktree back to origin after the push; branch deletion may be blocked in cron and can be left as harmless local cleanup. See `references/2026-06-live-origin-divergence-schema-migration.md`.
- If the finalizer refuses at `stage: missing_upstream_main` because `upstream/main` advanced between the pre-run script and finalizer fetch, do not bypass it. Rebase the isolated candidate onto the freshly fetched `upstream/main`, confirm it is clean and `git merge-base --is-ancestor upstream/main HEAD` succeeds, then rerun the finalizer against the isolated worktree. Do not move the live branch first; successful finalization schedules activation. If candidate-source config check reports a schema update, follow the config-migration loop above.
- If preflight divergence shows exactly one live-only `+` commit with subject `feat: add notes intake isolation and cron wake gate`, do not assume the live commit is unique. This can be the same false-positive class as the Telegram polling fix: repeated rebases rewrite the notes-intake commit over newer gateway/cron internals, so origin may already contain an equivalent rebased commit. Verify origin has the same subject plus anchors for `gateway/notes_intake.py` (`enrich_anything_inbox_image`), `gateway/run.py` (`is_anything_inbox_source` / `should_auto_new_session_for_capture`), cron wake-gate handling (`ready_count`), and the notes-intake / wake-gate regression tests. If equivalent, choose origin/worktree as the candidate, patch the wake-gate script equivalence guard if needed, sync/commit the personalization snapshot, rebase onto `upstream/main`, and finalize through the skill-owned finalizer.

## Known conflict patterns

- `gateway/notes_intake.py` can fail after upstream `tools/vision_tools.py` refactors remove/rename private helpers. If tests fail on `ImportError: cannot import name '_detect_image_mime_type' from 'tools.vision_tools'`, preserve Anything Inbox image routing by replacing the import with `_detect_image_mime_type_from_bytes` plus a local path-byte MIME helper in `gateway/notes_intake.py`; add/keep a regression asserting `_make_vision_messages()` sniffs PNG bytes rather than relying on suffix/default JPEG. Then rerun the focused notes-intake/wake-gate tests and finalize through `scripts/finalize_rebase_push.py`.
- `plugins/platforms/telegram/adapter.py` conflicts between upstream's reconnect-state contract (`connect(..., is_reconnect=...)`, `drop_pending_updates=not is_reconnect`) and Brayan's older `fix: preserve Telegram updates during polling startup` should preserve both layers: keep the upstream `is_reconnect` gateway contract, but keep Telegram polling startup at `drop_pending_updates=False` for both cold service restarts and watcher reconnects so queued Bot API updates are not silently discarded. Update Telegram tests to assert cold/reconnect preservation, update generic reconnect tests to avoid claiming every cold boot drops queues, and use the plugin adapter monkeypatch path `plugins.platforms.telegram.adapter.Application`. See `references/2026-06-telegram-polling-startup-preserve-queue-conflict.md`.
- If the Telegram polling conflict recurs after upstream has introduced resilient polling / degraded startup, preserve upstream's `_start_polling_resilient(...)` path and post-connect housekeeping tests; only change the helper argument to `drop_pending_updates=False`, keep both the housekeeping non-blocking test and the pending-update preservation test, and cancel heartbeat tasks in tests that call real `connect()`. See `references/2026-07-telegram-resilient-polling-conflict.md`.
- `AGENTS.md` top-of-file conflicts between upstream repo guidance and Brayan's personalization branch boundary rules should preserve both sides. Keep upstream's general repo instruction such as `**Never give up on the right solution.**`, keep Brayan's `## Brayan personalization branch rules` block near the top, and keep any upstream `## What Hermes Is` / contribution-rubric guidance rather than choosing one side. In autonomous cron, if broad script edits are blocked by approval, use narrow git/file operations: `git checkout --ours AGENTS.md`, targeted patch insertion of the Brayan block, conflict-marker search, then `GIT_EDITOR=true git rebase --continue`. See `references/2026-06-agents-upstream-rubric-conflict.md` for the concrete recovery pattern.
- `gateway/run.py` import conflicts between upstream gateway/provider additions and Brayan's notes-intake branch should preserve both sides when both imported symbols are still referenced. For the 2026-05-23 rebase, keep upstream `from hermes_cli.fallback_config import get_fallback_chain` and Brayan's `from gateway.notes_intake import enrich_anything_inbox_image, is_anything_inbox_source, load_notes_intake_settings, persist_audio_transcript, should_auto_new_session_for_capture` import block; this is an import-surface conflict, not a choice between fallback routing and Anything Inbox capture routing.
- `gateway/run.py` image-routing conflicts between upstream native image routing and Brayan's Anything Inbox image preprocessing should preserve both behaviors. Resolve the `if image_paths:` block as: first route Anything Inbox captures through `is_anything_inbox_source(source) and load_notes_intake_settings().enabled`, `enrich_anything_inbox_image(...)`, and the existing generic-vision fallback context block; otherwise keep the current upstream native/text routing with `_decide_image_input_mode(source=source, session_key=session_key)`. If upstream has migrated native attachments into `SessionState`, store native image paths with `self._session_state(session_key).persistent.native_image_paths = list(image_paths)` so `_consume_pending_native_image_paths()` can find them; only use the legacy `_pending_native_image_paths_by_session[session_key]` buffer when the current upstream consume path still reads that legacy view. Do not keep the older no-argument `_decide_image_input_mode()` call in the non-inbox branch after upstream added per-session model override support.
- `tests/cron/test_cron_script.py` empty-script-output conflicts can be caused by upstream removing stale tests while Brayan's branch preserves updated cron wake-gate behavior. Current intended behavior: `_run_job_script()` returns `(True, "")` for empty stdout, normal agent-mode `run_job()` treats empty script stdout as silent/`[SILENT]`, and `_build_job_prompt()` returns `None` for an empty successful pre-run script rather than injecting a "no output" prompt. When resolving a rebase conflict around `test_script_empty_output_noted` / `test_script_empty_output_skips_prompt`, preserve the `assert prompt is None` expectation if `cron/scheduler.py` still implements the empty-output skip at `_build_job_prompt()`.
- If the same test file conflicts because upstream added `_run_job_script()` coverage for UTF-8/emoji, invalid UTF-8, timeout, JSON, or empty stdout while Brayan's branch keeps wake-gate expectations, treat it as an additive test-cluster conflict: preserve all non-duplicated upstream `_run_job_script()` tests plus Brayan's `TestScriptWakeGate` and `_build_job_prompt(... ) is None` empty-output skip tests, then rerun the focused wake-gate/intake and full cron-tooling test sets before finalizing.

## Verification commands
Use the repo venv and clear repo-level pytest addopts where needed. These commands are for validating repairs or script/skill changes; they are not an instruction to rerun the pre-run script itself.
```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python -m py_compile ~/.hermes/scripts/hermes_upstream_rebase_ci.py /home/brayan/.hermes/hermes-agent/scripts/sync-brayan-personalization.py /home/brayan/.hermes/hermes-agent/scripts/apply-brayan-personalization.py /home/brayan/.hermes/skills/automation-agents/hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest tests/gateway/test_notes_intake_pipeline.py tests/plugins/test_notes_preprocessor_intake.py tests/cron/test_cron_script.py::TestScriptWakeGate -q -o 'addopts='
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest tests/cron/test_cron_script.py tests/tools/test_cronjob_tools.py tests/hermes_cli/test_cron.py -q -o 'addopts='
/home/brayan/.local/bin/hermes config check
```

Do not schedule or modify cron jobs from this run.
