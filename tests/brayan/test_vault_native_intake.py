"""Native intake full-operation ownership, real temporary Git + asyncio tasks."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import Mock

import pytest
from test_vault_ownership import ROOT,SCRIPTS,contract,write_contract,init_repo,git,load_module

PLUGIN=ROOT/'brayan-personalization/runtime/plugins/vault-ownership/__init__.py'


def setup(tmp_path,monkeypatch):
    sys.path.insert(0,str(SCRIPTS))
    repo,remote=init_repo(tmp_path)
    home=tmp_path/'hermes'
    cfg=contract(home,repo=repo)
    cfg.update(remote=str(remote),vault_path=str(repo),intake_allowed_paths=['inbox/'],intake_lock_wait_seconds=2)
    write_contract(home,cfg)
    monkeypatch.setenv('HERMES_HOME',str(home))
    plugin=load_module(PLUGIN,'native_intake_test_plugin')
    monkeypatch.setattr('gateway.notes_intake.is_anything_inbox_source',lambda source: source.chat_id=='inbox')
    event=SimpleNamespace(source=SimpleNamespace(chat_id='inbox',platform=SimpleNamespace(value='telegram')),message_id='capture-1',_gateway_turn_result={'completed':True},_gateway_turn_error=None)
    gateway=SimpleNamespace(_effective_busy_input_mode=lambda source:'queue')
    return plugin,cfg,repo,remote,event,gateway


@pytest.mark.asyncio
async def test_native_turn_lock_and_context_local_fence_publish_exact_intent(tmp_path,monkeypatch):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    path=repo/'inbox'/'capture.md'
    async def unrelated():
        return plugin.guard_tool('write_file',{'path':str(path),'content':'wrong'},session_id='other')
    other=asyncio.create_task(asyncio.Event().wait())
    other.cancel()
    with pytest.raises(asyncio.CancelledError): await other
    # Create the unrelated task before scope ContextVar exists.
    start=asyncio.Event()
    async def separate():
        await start.wait()
        return await unrelated()
    task=asyncio.create_task(separate())
    async with plugin.turn_scope(event=event,source=event.source,session_key='intake-key',gateway=gateway):
        start.set()
        assert (await task)['action']=='block'
        assert plugin.guard_tool('write_file',{'path':str(path),'content':'good'}) is None
        path.parent.mkdir()
        path.write_text('raw transcript and routed note\n')
        assert (Path(cfg['state_dir'])/'pending-owner.json').exists()
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()
    assert git(repo,'rev-parse','HEAD').stdout.strip()==git(repo,'ls-remote',str(remote),'refs/heads/main').stdout.split()[0]
    assert 'capture-1' in git(repo,'log','-1','--format=%B').stdout
    assert plugin.guard_tool('write_file',{'path':str(path)})['action']=='block'


@pytest.mark.asyncio
async def test_failed_native_turn_preserved_and_does_not_publish(tmp_path,monkeypatch):
    from gateway.turn_scope import TurnScopeError
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    base=git(repo,'rev-parse','HEAD').stdout
    event._gateway_turn_result={'completed':False,'failed':True}
    with pytest.raises(TurnScopeError,match='preserved'):
        async with plugin.turn_scope(event=event,source=event.source,session_key='key',gateway=gateway):
            (repo/'inbox').mkdir()
            (repo/'inbox'/'raw.md').write_text('retained')
    assert (repo/'inbox'/'raw.md').read_text()=='retained'
    assert git(repo,'rev-parse','HEAD').stdout==base
    with pytest.raises(TurnScopeError,match='preserved'):
        async with plugin.turn_scope(event=event,source=event.source,session_key='next',gateway=gateway):
            pytest.fail('Pending work was swept')


def test_contributor_file_reads_pin_real_snapshot_once(tmp_path,monkeypatch):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    import vault_contributions as vc
    cfg.update(role='contributor',owner_hostname='OtherOwner',vault_path=str(tmp_path/'mirror'))
    write_contract(Path(cfg['hermes_home']),cfg)
    first=git(repo,'rev-parse','HEAD').stdout.strip()
    vc.publish_snapshot(cfg,repo,first)
    initial=plugin.guard_tool('read_file',{'path':cfg['vault_path']+'/README.md'},session_id='reader')
    assert initial['action']=='modify'
    assert Path(initial['args']['path']).read_text()=='base\n'
    (repo/'README.md').write_text('new\n')
    git(repo,'add','README.md'); git(repo,'commit','-m','second')
    vc.publish_snapshot(cfg,repo,git(repo,'rev-parse','HEAD').stdout.strip())
    again=plugin.guard_tool('read_file',{'path':cfg['vault_path']+'/README.md'},session_id='reader')
    assert again==initial


@pytest.mark.asyncio
async def test_native_busy_wait_yields_loop_and_cancel_does_not_leak_lock(tmp_path,monkeypatch):
    from vault_ownership_common import owner_lock
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    entered=False
    async def contender():
        nonlocal entered
        async with plugin.turn_scope(event=event,source=event.source,session_key='key',gateway=gateway):
            entered=True
    with owner_lock(cfg):
        task=asyncio.create_task(contender())
        await asyncio.sleep(.1)
        assert not entered
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    with owner_lock(cfg): pass
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()


@pytest.mark.asyncio
async def test_clean_failure_does_not_wedge_next_capture(tmp_path,monkeypatch):
    from gateway.turn_scope import TurnScopeError
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    event._gateway_turn_result={'completed':False,'failed':True}
    with pytest.raises(TurnScopeError):
        async with plugin.turn_scope(event=event,source=event.source,session_key='failure',gateway=gateway):
            pass
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()
    event._gateway_turn_result={'completed':True}
    async with plugin.turn_scope(event=event,source=event.source,session_key='retry',gateway=gateway):
        pass


@pytest.mark.asyncio
async def test_body_exception_retains_native_exception_identity(tmp_path,monkeypatch):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    error=RuntimeError('native lease failure')
    with pytest.raises(RuntimeError) as caught:
        async with plugin.turn_scope(event=event,source=event.source,session_key='failure',gateway=gateway):
            raise error
    assert caught.value is error
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()


@pytest.mark.asyncio
async def test_agent_commit_is_preserved_not_silently_accepted(tmp_path,monkeypatch):
    from gateway.turn_scope import TurnScopeError
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    base=git(repo,'rev-parse','HEAD').stdout.strip()
    with pytest.raises(TurnScopeError):
        async with plugin.turn_scope(event=event,source=event.source,session_key='commit',gateway=gateway):
            (repo/'inbox').mkdir()
            (repo/'inbox'/'raw.md').write_text('agent committed')
            git(repo,'add','--all'); git(repo,'commit','-m','agent commit')
    assert (Path(cfg['state_dir'])/'pending-owner.json').exists()
    assert git(repo,'ls-remote',str(remote),'refs/heads/main').stdout.split()[0]==base


@pytest.mark.asyncio
async def test_final_cleanup_failure_is_visible_and_preserves_marker(tmp_path,monkeypatch):
    from gateway.turn_scope import run_scoped_turn
    from hermes_cli import plugins
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    monkeypatch.setattr(plugins,'iter_hook_callbacks',lambda name:(plugin.turn_scope,))
    def failure(holder):
        raise ValueError('cannot verify cgroup stopped')
    monkeypatch.setattr(plugin,'_close_terminals',failure)
    async def body(*args):
        event._gateway_turn_result={'completed':True}
        return 'native response'
    result=await run_scoped_turn(body,event,event.source,'cleanup',1,gateway=gateway)
    assert 'recovery' in result.lower()
    assert (Path(cfg['state_dir'])/'pending-owner.json').exists()


@pytest.mark.asyncio
async def test_cancel_during_begin_cleans_only_own_clean_marker(tmp_path,monkeypatch):
    import threading
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    original=plugin._begin
    started=threading.Event()
    release=threading.Event()
    def slow(*args):
        result=original(*args)
        started.set()
        release.wait(5)
        return result
    monkeypatch.setattr(plugin,'_begin',slow)
    async def turn():
        async with plugin.turn_scope(event=event,source=event.source,session_key='cancel',gateway=gateway):
            pytest.fail('Cancelled admission must not enter the native body')
    task=asyncio.create_task(turn())
    await asyncio.to_thread(started.wait,5)
    assert started.is_set()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError): await task
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()


def test_native_session_end_releases_only_ended_reader_pin(tmp_path,monkeypatch):
    from hermes_cli.plugins import PluginManager, PluginContext
    from hermes_cli.plugins_manifest import PluginManifest
    import vault_contributions as vc
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    cfg.update(role='contributor',owner_hostname='OtherOwner',vault_path=str(tmp_path/'mirror'))
    write_contract(Path(cfg['hermes_home']),cfg)
    base=git(repo,'rev-parse','HEAD').stdout.strip()
    vc.publish_snapshot(cfg,repo,base)
    first=plugin._pin(cfg,'reader-ended')
    running=plugin._pin(cfg,'reader-running')
    manager=PluginManager()
    ctx=PluginContext(PluginManifest(name='vault-ownership'),manager)
    plugin.register(ctx)
    assert tuple(manager.iter_hook_callbacks('on_session_end')), 'Supported native lifecycle hook must be registered'
    manager.invoke_hook('on_session_end',session_id='reader-ended',task_id='completed-turn')
    assert (cfg['hermes_home'],'reader-ended') not in plugin._pins
    assert not vc._pin_path(cfg,'reader-ended').exists()
    assert vc._pin_path(cfg,'reader-running').exists()
    assert plugin._pins[(cfg['hermes_home'],'reader-running')]['snapshot']==str(running)
    assert first.is_dir(), 'Release must never delete a snapshot directly'
    # Idempotent end and unidentified end do not release another running reader.
    manager.invoke_hook('on_session_end',session_id='reader-ended')
    manager.invoke_hook('on_session_end',session_id=None)
    assert vc._pin_path(cfg,'reader-running').exists()
    # A future native turn can acquire the new snapshot instead of stale cache.
    (repo/'README.md').write_text('updated snapshot\n')
    git(repo,'add','README.md');git(repo,'commit','-m','update')
    vc.publish_snapshot(cfg,repo,git(repo,'rev-parse','HEAD').stdout.strip())
    assert plugin._pin(cfg,'reader-ended') != first
    assert plugin._pin(cfg,'reader-running') == running
