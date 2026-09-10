"""Harmless real user-cgroup tests; no services or persistent configuration."""
import asyncio
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

import pytest
from test_vault_native_intake import setup


def bus_available():
    result = subprocess.run(['systemctl','--user','show-environment'], capture_output=True)
    return result.returncode == 0


@pytest.mark.asyncio
async def test_native_terminal_contains_detached_descendant_before_publication(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}')
    if not bus_available():
        pytest.skip('A working systemd user bus is required for this real containment test')
    plugin,cfg,repo,remote,event,gateway = setup(tmp_path,monkeypatch)
    pidfile = tmp_path/'descendant.pid'
    # Detached child deliberately closes inherited stdio, and outlives its shell.
    code = ('import os,time; from pathlib import Path; pid=os.fork(); '
            'os._exit(0) if pid else None; os.setsid(); '
            f'Path({str(pidfile)!r}).write_text(str(os.getpid())); '
            '[os.close(fd) for fd in (0,1,2)]; time.sleep(60)')
    async with plugin.turn_scope(event=event,source=event.source,session_key='terminal',gateway=gateway):
        args = dict(command=shlex.join([sys.executable,'-c',code]),timeout=10,workdir=str(repo))
        directive = plugin.guard_tool('terminal',args)
        assert directive['action']=='modify', directive
        result = await asyncio.to_thread(subprocess.run, directive['args']['command'],shell=True,capture_output=True,timeout=15)
        assert result.returncode==0, result.stderr
        for _ in range(100):
            if pidfile.exists(): break
            await asyncio.sleep(.01)
        assert pidfile.exists()
        pid=int(pidfile.read_text())
        assert Path(f'/proc/{pid}').exists()
        assert 'vault-intake-' in Path(f'/proc/{pid}/cgroup').read_text()
    # A zombie cannot write; the user manager/parent may reap asynchronously.
    proc=Path(f'/proc/{pid}/stat')
    assert not proc.exists() or proc.read_text().split(') ',1)[1].startswith('Z')
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()


@pytest.mark.asyncio
async def test_terminal_rejects_background_and_kernel_but_allows_python(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}')
    if not bus_available():
        pytest.skip('A working systemd user bus is required')
    plugin,cfg,repo,remote,event,gateway = setup(tmp_path,monkeypatch)
    async with plugin.turn_scope(event=event,source=event.source,session_key='terminal',gateway=gateway):
        assert plugin.guard_tool('terminal',dict(command='true',background=True))['action']=='block'
        assert plugin.guard_tool('execute_code',dict(code='pass'))['action']=='block'
        directive=plugin.guard_tool('terminal',dict(command='python3 -c "print(1)"'))
        assert directive['action']=='modify'
        assert 'systemd-run --user --scope' in directive['args']['command']


@pytest.mark.asyncio
async def test_closed_turn_context_and_alternate_spawners_fail_closed(tmp_path,monkeypatch):
    plugin,cfg,repo,remote,event,gateway = setup(tmp_path,monkeypatch)
    late=asyncio.Event()
    async def leaked():
        await late.wait()
        return plugin.guard_tool('terminal',dict(command='python3 -c "print(1)"'))
    async with plugin.turn_scope(event=event,source=event.source,session_key='terminal',gateway=gateway):
        for name in ('delegate_task','cronjob','cronjob_manage','tool_call'):
            assert plugin.guard_tool(name,dict(action='create'))['action']=='block'
        task=asyncio.create_task(leaked())
    late.set()
    assert (await task)['action']=='block'


@pytest.mark.asyncio
async def test_prepared_terminal_cannot_launch_after_scope_closes(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}')
    if not bus_available(): pytest.skip('A working user bus is required')
    plugin,cfg,repo,remote,event,gateway = setup(tmp_path,monkeypatch)
    sentinel=tmp_path/'must-not-exist'
    async with plugin.turn_scope(event=event,source=event.source,session_key='terminal',gateway=gateway):
        directive=plugin.guard_tool('terminal',dict(command=f'touch {shlex.quote(str(sentinel))}'))
    result=subprocess.run(directive['args']['command'],shell=True,capture_output=True)
    assert result.returncode==125
    assert not sentinel.exists()


@pytest.mark.asyncio
async def test_reentry_closes_crash_receipt_before_refusing_pending_work(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}')
    if not bus_available(): pytest.skip('A working user bus is required')
    plugin,cfg,repo,remote,event,gateway = setup(tmp_path,monkeypatch)
    real_close=plugin._close_terminals
    monkeypatch.setattr(plugin,'_close_terminals',lambda holder: None)
    holder=None
    event._gateway_turn_result={'failed':True}
    from gateway.turn_scope import TurnScopeError
    try:
        with pytest.raises(TurnScopeError):
            async with plugin.turn_scope(event=event,source=event.source,session_key='crash',gateway=gateway):
                (repo/'inbox').mkdir()
                (repo/'inbox'/'raw.md').write_text('preserve crashed capture')
                holder=plugin._holder.get()
                directive=plugin.guard_tool('terminal',dict(command='setsid sleep 60 >/dev/null 2>&1 &',timeout=10))
                result=await asyncio.to_thread(subprocess.run,directive['args']['command'],shell=True,capture_output=True,timeout=15)
                assert result.returncode==0
        unit=holder['units'][0]
        assert plugin._scope_state(unit)['ActiveState']=='active'
        monkeypatch.setattr(plugin,'_close_terminals',real_close)
        with pytest.raises(TurnScopeError):
            async with plugin.turn_scope(event=event,source=event.source,session_key='next',gateway=gateway):
                pytest.fail('Pending work must remain blocked')
        assert plugin._scope_state(unit).get('ActiveState') in {'inactive','failed'}
        assert (Path(cfg['state_dir'])/'pending-owner.json').exists()
    finally:
        if holder is not None: real_close(holder)



def test_disappearing_unit_during_stop_is_success(tmp_path,monkeypatch):
    plugin,*_=setup(tmp_path,monkeypatch)
    states=iter([dict(LoadState='loaded',ActiveState='active'), dict(LoadState='not-found',ActiveState='inactive')])
    monkeypatch.setattr(plugin,'_scope_state',lambda unit: next(states))
    def vanished(*args,**kwargs):
        if kwargs.get('check'): raise subprocess.CalledProcessError(5,args[0])
        return subprocess.CompletedProcess(args[0],5,stdout='',stderr='not loaded')
    monkeypatch.setattr(plugin.subprocess,'run',vanished)
    plugin._stop_unit('vault-intake-test.scope')
