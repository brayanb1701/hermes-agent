"""Native intake ownership and file-tool accident guards (not a sandbox).

No capture queue. Native media preprocessing and the native agent stay intact.
Only the context holding the full-operation owner lock may mutate canonical.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import shlex
import subprocess
import threading
import time
import sys
import uuid

log = logging.getLogger('vault_ownership')
_holder = ContextVar('vault_intake_holder', default=None)
_pins = {}


def get_contract():
    from hermes_constants import get_hermes_home
    home = get_hermes_home()
    scripts = str(home / 'scripts')
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from vault_ownership_common import load_contract
    return load_contract(home)


async def _owned_io(fn, *args):
    """Cancellation never releases the lock while its I/O thread still writes."""
    task = asyncio.create_task(asyncio.to_thread(fn, *args))
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
            if task.done():
                result = task.result()
                break
    if cancelled:
        raise asyncio.CancelledError
    return result


def _begin(contract, event, session_key):
    from vault_ownership import git, require_writable_canonical, _atomic_write_json, _reconcile_locked
    state, root = Path(contract['state_dir']), Path(contract['repo_path'])
    if Path(contract['vault_path']).resolve() != root.resolve():
        raise ValueError('Native owner vault must be its canonical checkout')
    require_writable_canonical(root)
    _recover_terminals(state)
    pending = state / 'pending-owner.json'
    if pending.exists():
        from vault_incident_alerts import reconcile_for_writer
        from vault_ownership import OwnershipError, _blocked_dispatch
        try:
            reconcile_for_writer(contract)
        except OwnershipError as exc:
            _blocked_dispatch(contract,'native-intake',exc)
            raise
    if git(root, 'status', '--porcelain'):
        raise ValueError('Canonical checkout is dirty; preserved without sweeping')
    git(root, 'fetch', '--no-tags', contract['remote'], contract['branch'])
    base = git(root, 'rev-parse', 'FETCH_HEAD')
    if git(root, 'rev-parse', 'HEAD') != base:
        raise ValueError('Canonical head differs from published main')
    intent = dict(id=uuid.uuid4().hex, session_key=session_key,
                  message_id=str(event.message_id), base=base, kind='native-intake',
                  version=2, phase='editing', terminal_id=uuid.uuid4().hex, terminal_units=[])
    _atomic_write_json(pending,intent)
    return intent


def _finish(contract, intent):
    from vault_ownership import git, validate_diff, publish, _read_json, _marker_phase, _fsync_directory
    from vault_intake_recovery import terminal_units_empty
    pending=Path(contract['state_dir'])/'pending-owner.json'
    intent=_read_json(pending,'native intake journal')
    terminal_units_empty(intent)
    root = Path(contract['repo_path'])
    if git(root, 'rev-parse', 'HEAD') != intent['base']:
        raise ValueError('Native agent changed Git HEAD; preserve for independent recovery')
    names = validate_diff(root, contract['intake_allowed_paths'])
    if names:
        intent=_marker_phase(pending,intent,'committed')
        git(root, 'commit', '-m', 'Native notes intake\n\n'
            f"Source-Host: {contract['hostname']}\nSession: {intent['id']}\n"
            f"Capture-ID: {intent['message_id']}\nBase-SHA: {intent['base']}")
        publish(root, contract, intent['base'])
        _marker_phase(pending,intent,'published')
    pending.unlink(); _fsync_directory(pending.parent)


def _clear_clean_failure(contract, intent):
    from vault_ownership import git, _read_json, _reconcile_locked
    pending=Path(contract['state_dir'])/'pending-owner.json'
    if not pending.exists(): return
    current=_read_json(pending,'native intake journal')
    if current.get('id')!=intent['id']: raise ValueError('Intake journal identity changed')
    root = Path(contract['repo_path'])
    if git(root, 'rev-parse', 'HEAD') == intent['base'] and not git(root, 'status', '--porcelain'):
        _reconcile_locked(contract,expected_run=intent['id'])


def _scope_state(unit):
    result = subprocess.run(['systemctl', '--user', 'show', unit, '--property=LoadState',
                             '--property=ActiveState', '--property=ControlGroup'],
                            text=True, capture_output=True, timeout=10)
    fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if fields.get('LoadState') == 'not-found':
        return fields
    if result.returncode or 'ActiveState' not in fields:
        raise ValueError('Cannot verify owned transient unit state')
    return fields


def _stop_unit(unit):
    fields = _scope_state(unit)
    if fields.get('LoadState') == 'not-found':
        return
    subprocess.run(['systemctl', '--user', 'stop', unit], check=False,
                   capture_output=True, timeout=15)
    fields = _scope_state(unit)
    if fields.get('LoadState') != 'not-found' and fields.get('ActiveState') not in {'inactive', 'failed'}:
        raise ValueError('Owned transient unit is still active')
    group = fields.get('ControlGroup')
    if group:
        events = Path('/sys/fs/cgroup') / group.lstrip('/') / 'cgroup.events'
        if events.exists() and 'populated 1' in events.read_text():
            raise ValueError('Owned transient cgroup still contains descendants')


def _close_terminals(holder):
    # Close admission before cleanup. Delayed tool dispatches check this durable
    # sentinel under the shared launch gate before creating any transient scope.
    with holder['mutex']:
        holder['active'] = False
        if holder.get('cleaned'):
            return
        if not holder['units']:
            return
        holder['open'].unlink(missing_ok=True)
        units = list(holder['units'])
    deadline = time.monotonic() + 30
    with holder['gate'].open('a+') as gate:
        while True:
            for unit in units:
                _stop_unit(unit)
            try:
                fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError('Owned terminal launch did not quiesce; recovery required')
                time.sleep(.05)
        # A launch holding the gate may have registered between the first stop
        # and exclusive acquisition. No later launch can pass the closed flag.
        for unit in units:
            _stop_unit(unit)
        (holder['directory']/'cleaned').touch()
        holder['cleaned'] = True


def _recover_terminals(state):
    for receipt in (state/'terminal-scopes').glob('*/units.json'):
        directory = receipt.parent
        if (directory/'cleaned').exists():
            continue
        units = json.loads(receipt.read_text())['units']
        if not isinstance(units, list) or any(not isinstance(unit, str) or not re.fullmatch(
                r'vault-intake-' + re.escape(directory.name) + r'-[0-9a-f]{32}\.scope', unit) for unit in units):
            raise ValueError('Invalid owned transient unit receipt; refusing broad cleanup')
        _close_terminals(dict(active=False, units=units, mutex=threading.Lock(),
                              directory=directory, open=directory/'open', gate=directory/'launch.lock'))


def _terminal_directive(holder, args):
    if args.get('background') or args.get('pty'):
        return {'action':'block', 'message':'Native intake terminal must be foreground, non-PTY; detached descendants are stopped before publication.'}
    command = args.get('command')
    if not isinstance(command, str) or not command.strip():
        raise ValueError('Terminal command is required')
    timeout = float(args.get('timeout') or 180)
    if not 0 < timeout <= 600:
        raise ValueError('Native intake requires a finite terminal timeout up to 600 seconds')
    with holder['mutex']:
        if not holder['active']:
            raise ValueError('Native intake terminal admission is closed')
        unit = f"vault-intake-{holder['id']}-{uuid.uuid4().hex}.scope"
        holder['units'].append(unit)
        holder['directory'].mkdir(parents=True, exist_ok=True)
        holder['gate'].touch(exist_ok=True)
        holder['open'].touch(exist_ok=True)
        from vault_ownership import _atomic_write_json, _read_json
        _atomic_write_json(holder['receipt'],{'units':holder['units']})
        marker=_read_json(holder['pending'],'native intake journal')
        if marker['terminal_id']!=holder['id']: raise ValueError('Intake terminal identity changed')
        _atomic_write_json(holder['pending'],dict(marker,terminal_units=list(holder['units'])))
    bounded = shlex.join(['systemd-run', '--user', '--scope', '--quiet', '--collect',
                         f'--unit={unit}', f'--property=RuntimeMaxSec={timeout + 15:g}',
                         '--property=TimeoutStopSec=5', '--', '/bin/bash', '-c', command])
    guarded = f'test -f {shlex.quote(str(holder["open"]))} || exit 125; exec {bounded}'
    wrapped = shlex.join(['flock', '--shared', str(holder['gate']), '/bin/bash', '-c', guarded])
    return {'action':'modify', 'args':dict(args, command=wrapped, background=False, pty=False)}


@asynccontextmanager
async def turn_scope(event, source, session_key, gateway, **kwargs):
    from gateway.notes_intake import is_anything_inbox_source
    from gateway.turn_scope import TurnScopeError
    if not is_anything_inbox_source(source):
        yield
        return
    try:
        contract = get_contract()
        from vault_ownership_common import require_owner
        require_owner(contract)
        if gateway._effective_busy_input_mode(source) != 'queue':
            raise ValueError('Native intake requires gateway busy_input_mode=queue')
        if not contract.get('intake_allowed_paths'):
            raise ValueError('Native intake requires explicit intake_allowed_paths')
    except Exception as exc:
        log.error('Native intake admission refused: %s', exc)
        raise TurnScopeError('This capture was not processed: ownership configuration is invalid. Repair it and resend.') from exc
    state = Path(contract['state_dir'])
    state.mkdir(parents=True, exist_ok=True)
    lock = (state / 'owner.lock').open('a+')
    directory = state / 'terminal-scopes' / uuid.uuid4().hex
    holder = dict(active=False, root=Path(contract['repo_path']), id=directory.name,
                  directory=directory, gate=directory/'launch.lock', open=directory/'open',
                  receipt=directory/'units.json', units=[], mutex=threading.Lock())
    token = None
    intent = None
    body_error = False
    acquired = False
    try:
        deadline = asyncio.get_running_loop().time() + float(contract.get('intake_lock_wait_seconds', 120))
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TurnScopeError('This capture was not processed because another owner operation is still running. Please resend after it finishes.')
                await asyncio.sleep(.05)
        def begin_owned():
            nonlocal intent
            intent = _begin(contract, event, session_key)
            directory=state/'terminal-scopes'/intent['terminal_id']
            holder.update(id=intent['terminal_id'],directory=directory,gate=directory/'launch.lock',
                          open=directory/'open',receipt=directory/'units.json',pending=state/'pending-owner.json')
        await _owned_io(begin_owned)
        holder['active'] = True
        token = _holder.set(holder)
        try:
            yield
        except BaseException:
            body_error = True
            raise
        await _owned_io(_close_terminals, holder)
        outcome = getattr(event, '_gateway_turn_result', None)
        if (getattr(event, '_gateway_turn_error', None) is not None or not isinstance(outcome, dict)
                or outcome.get('completed') is not True or outcome.get('failed') or outcome.get('interrupted')):
            raise TurnScopeError('Capture work was preserved locally but not published: the native turn did not complete successfully. Recovery is required.')
        await _owned_io(_finish, contract, intent)
    except asyncio.CancelledError:
        raise
    except TurnScopeError:
        raise
    except Exception as exc:
        if body_error:
            raise
        log.exception('Native intake ownership operation failed')
        raise TurnScopeError('Capture work was preserved, not automatically swept or published. Ownership recovery is required before another write.') from exc
    finally:
        try:
            def cleanup_owned():
                _close_terminals(holder)
                if intent is not None:
                    _clear_clean_failure(contract, intent)
            await _owned_io(cleanup_owned)
        except Exception as exc:
            log.exception('Native intake terminal cleanup could not be verified')
            raise TurnScopeError('Capture cleanup could not be verified. Work is preserved and owner recovery is required before another write.') from exc
        finally:
            holder['active'] = False
            if token is not None:
                _holder.reset(token)
            if acquired:
                fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()


def pre_dispatch(event, gateway=None, **kwargs):
    # Native authorization and the async turn scope own admission. Never skip a
    # message here (this hook runs BEFORE auth and has no retry/queue directive).
    return None


def _pin(contract, session_id):
    if not session_id:
        raise ValueError('Snapshot reads require a stable session id')
    from vault_contributions import pin_snapshot
    key = (contract['hermes_home'], str(session_id))
    if key not in _pins:
        _pins[key] = pin_snapshot(contract, str(session_id))
    return Path(_pins[key]['snapshot'])


def guard_tool(tool_name, args, session_id=None, **kwargs):
    if tool_name=='browser_exec' and os.environ.get('BU_NAME')=='_default' and os.environ.get('BH_RUNTIME_DIR_SHARED')=='1':
        if args.get('session')=='default':
            return {'action':'modify','args':dict(args,session='')}
        return None
    holder = _holder.get()
    if holder is not None:
        if not holder['active']:
            return {'action':'block', 'message':'This native intake turn has closed; no further tools may run in its inherited context.'}
        if tool_name in {'delegate_task', 'cronjob', 'cronjob_manage', 'tool_call'}:
            return {'action':'block', 'message':'Native intake cannot create asynchronous writers. Use bounded foreground terminal commands or native file tools.'}
        if tool_name in {'process', 'process_manage'} and args.get('action') not in {'poll','log','wait','kill','list'}:
            return {'action':'block', 'message':'Native intake permits process observation/cleanup only, not further process input.'}
    if tool_name not in {'write_file', 'patch', 'read_file', 'search_files', 'terminal', 'execute_code'}:
        return None
    try:
        contract = get_contract()
        roots = [Path(contract[key]).resolve() for key in ('vault_path', 'repo_path', 'snapshot_root')]
        holder = _holder.get()
        active = holder is not None and holder['active'] and holder['root'] == Path(contract['repo_path'])
        if tool_name in {'terminal', 'execute_code'}:
            if active:
                if tool_name == 'terminal':
                    return _terminal_directive(holder, args)
                return {'action':'block', 'message':'Shared-kernel execute_code bypasses native process containment. Use a foreground terminal Python command instead.'}
            command = args.get('command') or args.get('code') or ''
            if not isinstance(command, str):
                return {'action':'block', 'message':'Command content must be text.'}
            workdir = args.get('workdir')
            if workdir and any(Path(workdir).expanduser().resolve().is_relative_to(root) for root in roots):
                return {'action':'block', 'message':'Use pinned file tools for canonical reads or an isolated contribution workspace for writes.'}
            if any(contract[key] in command for key in ('vault_path', 'repo_path', 'snapshot_root')):
                return {'action':'block', 'message':'Use pinned file tools for canonical reads or an isolated contribution workspace for writes.'}
        paths = []
        if tool_name in {'write_file', 'patch'}:
            paths = [args.get('path', '')]
            patch_text = args.get('patch')
            if patch_text is not None and not isinstance(patch_text, str):
                return {'action':'block', 'message':'Patch content must be text.'}
            paths += re.findall(r'^\*\*\* (?:Update|Add|Delete) File: (.+)$', patch_text or '', re.M)
        for value in paths:
            if not value:
                continue
            path = Path(value).expanduser()
            if not path.is_absolute():
                # Gateway cwd is not necessarily this turn's tool cwd.
                return {'action':'block', 'message':'Ownership write guard requires absolute file paths.'}
            resolved = path.resolve()
            protected = any(resolved.is_relative_to(root) for root in roots)
            if protected and not (active and resolved.is_relative_to(holder['root'])
                                  and not resolved.is_relative_to(Path(contract['snapshot_root']))):
                return {'action':'block', 'message':'Canonical vault and snapshots are read-only outside the native intake scope holder.'}
        if tool_name in {'read_file', 'search_files'} and args.get('path'):
            path = Path(os.path.abspath(os.path.expanduser(args['path'])))
            vault = Path(contract['vault_path'])
            if path.is_relative_to(vault) and not active:
                # Owner can read its canonical checkout; only contributor reads
                # must resolve/pin once per session against immutable history.
                if contract['role'] == 'contributor':
                    return {'action':'modify', 'args':{'path':str(_pin(contract, session_id) / path.relative_to(vault))}}
        return None
    except Exception as exc:
        log.exception('Ownership file-tool validation failed')
        return {'action':'block', 'message':f'Ownership guard error ({type(exc).__name__}); see agent.log. No tool action was allowed.'}


def end_session(session_id=None, **kwargs):
    """Release only the native lifecycle's exact reader lease, never snapshots.

    Hermes emits on_session_end at completed conversation-turn finalization.
    Other session pins survive; a later turn acquires a fresh immutable snapshot.
    Keep cached evidence if durable release fails so recovery can retry safely.
    """
    if session_id is None or not str(session_id):
        return None
    contract = get_contract()
    from vault_contributions import release_snapshot
    release_snapshot(contract, str(session_id))
    _pins.pop((contract['hermes_home'], str(session_id)), None)
    return None


def register(ctx):
    ctx.register_hook('gateway_turn_scope', turn_scope)
    ctx.register_hook('pre_tool_call', guard_tool)
    ctx.register_hook('on_session_end', end_session)
