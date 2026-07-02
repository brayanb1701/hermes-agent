# 2026-07 Telegram resilient polling conflict

## Trigger

Daily `hermes-upstream-rebase-ci` woke at `stage: rebase` while applying Brayan's commit `fix: preserve Telegram updates during polling startup` onto upstream/main.

Conflicted paths:

- `plugins/platforms/telegram/adapter.py`
- `tests/gateway/test_telegram_conflict.py`
- `tests/gateway/test_platform_reconnect.py` was modified by the replayed commit but not conflicted.

## Root cause

Upstream had changed Telegram polling startup to use the newer resilient helper and deferred post-connect housekeeping:

- `polling_started = await self._start_polling_resilient(...)`
- `if not polling_started: ... degraded Telegram mode ...`
- `_start_post_connect_housekeeping()` after the transport is up

Brayan's older patch was written against a direct call to:

- `await self._app.updater.start_polling(...)`

The semantic conflict was not whether to keep the helper. The durable requirement is: preserve upstream's resilient helper/housekeeping architecture while keeping Brayan's `drop_pending_updates=False` behavior for both cold starts and reconnects.

## Correct resolution

In `plugins/platforms/telegram/adapter.py`, keep the upstream helper call and set queue preservation explicitly:

```python
polling_started = await self._start_polling_resilient(
    # Preserve the Bot API queue on both cold service restarts
    # and watcher reconnects so messages sent while the gateway
    # is offline are delivered instead of silently discarded.
    drop_pending_updates=False,
    error_callback=_polling_error_callback,
)
if not polling_started:
    logger.warning(...)
```

Do **not** revert to direct `self._app.updater.start_polling(...)`; that loses upstream's resilient startup/degraded-mode behavior.

In `tests/gateway/test_telegram_conflict.py`, keep both tests rather than choosing one:

1. Upstream/post-connect regression:
   - `test_connect_does_not_block_on_post_connect_housekeeping`
   - ensures hanging housekeeping does not block `connect()` and disconnect cancels the task.
2. Brayan queue-preservation regression:
   - `test_polling_connect_preserves_pending_updates`
   - asserts `delete_webhook(drop_pending_updates=False)` and `start_polling(... drop_pending_updates=False)`.
   - explicitly call `await _cancel_heartbeat(adapter)` before test exit so the polling heartbeat task does not leak/busy-spin.

Keep the broader cold/reconnect queue tests near `_build_polling_app()`:

- `test_cold_connect_preserves_pending_updates`
- `test_reconnect_preserves_pending_updates`

## Verification used

From the rebased candidate/worktree:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python -m py_compile \
  plugins/platforms/telegram/adapter.py \
  tests/gateway/test_telegram_conflict.py \
  tests/gateway/test_platform_reconnect.py

/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/gateway/test_telegram_conflict.py \
  tests/gateway/test_platform_reconnect.py \
  tests/gateway/test_notes_intake_pipeline.py \
  tests/plugins/test_notes_preprocessor_intake.py \
  tests/cron/test_cron_script.py::TestScriptWakeGate \
  -q -o 'addopts='

/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/cron/test_cron_script.py \
  tests/tools/test_cronjob_tools.py \
  tests/hermes_cli/test_cron.py \
  -q -o 'addopts='
```

Then run the skill-owned finalizer with `--apply`. If it refuses because live `HEAD` does not yet contain `upstream/main`, compare the isolated candidate, create a backup ref, move the live branch with guarded `git update-ref` + `git read-tree --reset -u HEAD`, and rerun the finalizer. Do not bypass the finalizer with a direct force push.
