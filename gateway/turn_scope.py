"""Async plugin resources spanning native preprocessing and one gateway turn.

Unlike observer hooks these contexts fail closed and unwind on cancellation.
Callbacks must only construct an async context manager; blocking work belongs
inside it off-loop. A TurnScopeError is a user-visible refusal/finalization error.
"""
from contextlib import AsyncExitStack
import logging

logger = logging.getLogger(__name__)


class TurnScopeError(RuntimeError):
    """Safe user-facing refusal or retained-work finalization notice."""


async def run_scoped_turn(body, event, source, session_key, generation, *, gateway):
    from hermes_cli.plugins import iter_hook_callbacks
    from hermes_cli.plugins_dispatch import PluginDispatchMixin
    payload = dict(event=event, source=source, session_key=session_key, gateway=gateway)
    # Reset reused event objects so prior success can never authorize this turn.
    event._gateway_turn_result = None
    event._gateway_turn_error = None
    try:
        async with AsyncExitStack() as stack:
            for callback in iter_hook_callbacks('gateway_turn_scope'):
                scope = PluginDispatchMixin._invoke_hook_callback(callback, payload)
                if scope is not None:
                    await stack.enter_async_context(scope)
            return await body(event, source, session_key, generation)
    except TurnScopeError as exc:
        logger.warning('Gateway turn scope refused or failed for %s: %s', session_key, exc)
        return str(exc)
