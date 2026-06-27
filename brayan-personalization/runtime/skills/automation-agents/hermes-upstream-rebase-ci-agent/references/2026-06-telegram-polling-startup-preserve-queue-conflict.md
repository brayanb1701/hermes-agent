# 2026-06 Telegram polling startup preserve-queue conflict

## Context

During the daily `hermes-upstream-rebase-ci` exception path, the isolated worktree failed rebasing Brayan's personalization branch onto `upstream/main` while applying the older Brayan commit:

- `fix: preserve Telegram updates during polling startup`
- conflicted file: `plugins/platforms/telegram/adapter.py`

Upstream had since added a broader reconnect contract:

- `BasePlatformAdapter.connect(*, is_reconnect: bool = False)`
- gateway reconnect watcher calls adapters with `is_reconnect=True`
- Telegram bootstrap used `drop_pending_updates=not is_reconnect`
- tests asserted cold boot defaults to `is_reconnect=False` and watcher reconnect uses `True`

Brayan's local fix asserted a stronger behavior: Telegram polling startup should not drop Bot API queued messages even on cold service restart, because gateway downtime/restart can otherwise silently lose messages sent while Hermes was down.

## Resolution rule

Preserve the upstream reconnect contract, but keep Brayan's stronger Telegram queue-preservation behavior for polling startup:

```python
await self._app.updater.start_polling(
    allowed_updates=Update.ALL_TYPES,
    # Preserve the Bot API queue on both cold service restarts
    # and watcher reconnects so messages sent while the gateway
    # is offline are delivered instead of silently discarded.
    drop_pending_updates=False,
    error_callback=_polling_error_callback,
)
```

Update the Telegram `connect()` docstring so it does not claim cold first boot drops the stale Bot API queue. It should say `is_reconnect` is still the gateway reconnect-state contract, while Telegram polling preserves the Bot API queue in both states.

## Test updates

Keep/adjust tests so all three behaviors are explicit:

- initial polling startup preserves pending updates
- cold connect preserves pending updates
- reconnect preserves pending updates

When patching mocks after the adapter moved into plugins, use:

```python
monkeypatch.setattr(
    "plugins.platforms.telegram.adapter.Application",
    SimpleNamespace(builder=MagicMock(return_value=builder)),
)
```

not the old `gateway.platforms.telegram.Application` path.

Also update generic reconnect tests so they only assert the cold path defaults `is_reconnect=False`; they should not assert that every platform must drop a stale queue on cold boot. Queue behavior is adapter-specific.

## Verification used

Focused checks that caught/guarded the resolution:

```bash
/home/brayan/.hermes/hermes-agent/venv/bin/python -m pytest \
  tests/gateway/test_telegram_conflict.py::test_polling_connect_preserves_pending_updates \
  tests/gateway/test_telegram_conflict.py::test_cold_connect_preserves_pending_updates \
  tests/gateway/test_telegram_conflict.py::test_reconnect_preserves_pending_updates \
  tests/gateway/test_platform_reconnect.py::TestPlatformReconnectWatcher::test_reconnect_passes_is_reconnect_true \
  tests/gateway/test_platform_reconnect.py::TestPlatformReconnectWatcher::test_cold_connect_defaults_to_is_reconnect_false \
  -q -o 'addopts='
```

Then run the standard finalizer verification/finalizer path from the main skill.
