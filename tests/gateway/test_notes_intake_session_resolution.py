"""Capture isolation remains on the active session-preparation path."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

# Bootstrap before per-test home guards are installed.
import gateway.run  # noqa: F401
from gateway.run_turn_prepare import GatewayTurnPrepareMixin


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [False, True])
async def test_capture_reset_respects_strict_session_pin(monkeypatch, strict):
    entry = SimpleNamespace(session_key="capture-key", session_id="pinned-id")
    store = SimpleNamespace(
        lookup_by_session_key=AsyncMock(return_value=entry),
        reset_session=AsyncMock(return_value=entry),
        get_or_create_session=AsyncMock(return_value=entry),
    )
    runner = SimpleNamespace(
        async_session_store=store,
        _session_key_for_source=lambda source: "capture-key",
        _cache_session_source=Mock(),
        _is_telegram_topic_lane=lambda source: False,
    )
    event = SimpleNamespace(metadata={
        "gateway_session_key": "capture-key",
        "gateway_session_id": "pinned-id" if strict else "",
        "gateway_session_strict": strict,
    })
    monkeypatch.setattr("gateway.run.should_auto_new_session_for_capture", lambda source: True)
    monkeypatch.setattr("gateway.run_heartbeat_acceptance.resolve_heartbeat_owner", AsyncMock(return_value=True))
    source = SimpleNamespace()
    result = await GatewayTurnPrepareMixin._hmwa_resolve_session(runner, event, source)
    assert result == (source, entry, "capture-key")
    if strict:
        store.reset_session.assert_not_awaited()
        store.lookup_by_session_key.assert_awaited_once_with("capture-key")
    else:
        store.reset_session.assert_awaited_once_with("capture-key")
    store.get_or_create_session.assert_not_awaited()
