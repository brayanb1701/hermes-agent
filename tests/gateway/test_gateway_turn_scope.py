"""Generic native turn resource scopes surround preprocessing and unwind."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_scope_precedes_native_body_and_finalization_failure_is_visible(monkeypatch):
    from gateway.turn_scope import run_scoped_turn, TurnScopeError
    from hermes_cli import plugins
    from hermes_cli.plugins import PluginManager, PluginContext
    manager=PluginManager()
    from hermes_cli.plugins_manifest import PluginManifest
    context=PluginContext(PluginManifest(name='test-turn-scope'),manager)
    calls=[]
    @asynccontextmanager
    async def scope(event):
        calls.append('enter')
        yield
        calls.append('publish')
        raise TurnScopeError('Publication failed; retained for recovery')
    context.register_hook('gateway_turn_scope', scope)
    monkeypatch.setattr(plugins,'iter_hook_callbacks',manager.iter_hook_callbacks)
    async def body(*args):
        calls.append('native-preprocess-and-turn')
        return 'finished'
    result=await run_scoped_turn(body,SimpleNamespace(),None,'key',1,gateway=None)
    assert result=='Publication failed; retained for recovery'
    assert calls==['enter','native-preprocess-and-turn','publish']


@pytest.mark.asyncio
async def test_real_inbound_dispatch_runs_scope_before_native_preprocess(monkeypatch):
    from gateway.run_inbound import GatewayInboundMixin
    from hermes_cli import plugins
    event=SimpleNamespace()
    source=SimpleNamespace()
    runner=MagicMock()
    runner._hm_admit_event=AsyncMock(return_value=(event,source,True))
    runner._hm_estop_gate.return_value=None
    runner._hm_pending_reply_intercepts=AsyncMock(return_value=None)
    runner._is_session_running.return_value=False
    runner._hm_dispatch_idle_commands=AsyncMock(return_value=(False,None))
    runner._claim_active_session_slot.return_value=(None,None)
    runner._hm_rescue_orphaned_fifo.return_value=(event,source,True)
    runner._clear_durable_active_turn=AsyncMock()
    runner._run_post_turn_hooks=AsyncMock()
    active=False
    @asynccontextmanager
    async def scope(**kwargs):
        nonlocal active
        active=True
        try: yield
        finally: active=False
    monkeypatch.setattr(plugins,'iter_hook_callbacks',lambda name:(scope,))
    async def preprocess(*args):
        assert active, 'Native raw preprocessing ran outside the scope'
        return 'native reply'
    runner._handle_message_with_agent=preprocess
    assert await GatewayInboundMixin._handle_message(runner,event)=='native reply'
    assert not active
    runner._release_turn_lease.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('raises', [False, True])
async def test_native_caught_failure_exposes_structured_scope_outcome(monkeypatch,tmp_path,raises):
    from tests.gateway.test_42039_duplicate_user_message import _bootstrap,_event,_source
    runner=_bootstrap(monkeypatch,tmp_path)
    event=_event()
    result={'completed':False,'failed':True,'final_response':None,'error':'test failure','messages':[],'history_offset':0,'last_prompt_tokens':0}
    runner._run_agent=AsyncMock(side_effect=RuntimeError('test failure')) if raises else AsyncMock(return_value=result)
    await runner._handle_message_with_agent(event,_source(),'agent:main:telegram:group:-1001:12345',1)
    if raises:
        assert isinstance(getattr(event,'_gateway_turn_error',None),RuntimeError)
    else:
        assert getattr(event,'_gateway_turn_result',None)==result


@pytest.mark.asyncio
async def test_cancel_releases_scope_without_running_body(monkeypatch):
    from gateway.turn_scope import run_scoped_turn
    from hermes_cli import plugins
    entered=asyncio.Event()
    released=asyncio.Event()
    @asynccontextmanager
    async def scope(**kwargs):
        try:
            entered.set()
            await asyncio.Event().wait()
            yield
        finally:
            released.set()
    monkeypatch.setattr(plugins,'iter_hook_callbacks',lambda name:(scope,))
    body=AsyncMock()
    task=asyncio.create_task(run_scoped_turn(body,SimpleNamespace(),None,'key',1,gateway=None))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert released.is_set()
    body.assert_not_called()
