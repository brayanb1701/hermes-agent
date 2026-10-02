"""Exact native run scopes. Cooperative lifecycle boundary, never a sandbox.

Explicit systemd/D-Bus launches and same-user cgroup/file writes can escape.
The wrapper stays outside the worker scope and closes launch admission first.
"""
from __future__ import annotations
import contextlib
import fcntl
import os
from pathlib import Path
import re
import subprocess
import time
from vault_ownership_common import OwnershipError


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def manager_ready():
    if not os.environ.get('XDG_RUNTIME_DIR') or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        raise OwnershipError('Native owner execution requires an explicit user systemd bus/runtime')
    result = subprocess.run(['systemctl','--user','show','app.slice','--property=ControlGroup'],
                            text=True,capture_output=True,timeout=10)
    if result.returncode or not result.stdout.strip().startswith('ControlGroup=/'):
        raise OwnershipError('Native owner execution requires a reachable user systemd manager')
    return result.stdout.strip().split('=',1)[1]


def scope_intent(run, run_dir):
    if not re.fullmatch('[0-9a-f]{32}',run):
        raise OwnershipError('Invalid run scope identity')
    unit = f'vault-run-{run}.scope'
    group = f'/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice/{unit}'
    return {'unit':unit,'boot_id':boot_id(),'expected_cgroup':group,
            'launch_gate':str(Path(run_dir)/'launch.lock'),'admission':str(Path(run_dir)/'launch.open')}


def validate_intent(intent, run, run_dir):
    expected = scope_intent(run,run_dir)
    if (not isinstance(intent,dict) or set(intent)-set(expected)-{'booking'}
            or any(intent.get(k)!=v for k,v in expected.items() if k!='boot_id')
            or not isinstance(intent.get('boot_id'),str)
            or not re.fullmatch('[0-9a-f-]{36}',intent['boot_id'])):
        raise OwnershipError('Run scope intent identity is invalid')
    booking = intent.get('booking')
    if booking is not None and (not isinstance(booking,dict)
            or set(booking)!={'pid','start_time','cgroup','invocation_id'}
            or type(booking['pid']) is not int or booking['pid']<=0
            or type(booking['start_time']) not in {float,int} or booking['start_time']<=0
            or booking['cgroup']!=expected['expected_cgroup']
            or not re.fullmatch('[0-9a-f]{32}',str(booking['invocation_id']))):
        raise OwnershipError('Run scope booking identity is invalid')
    return intent


def scope_state(unit):
    r=subprocess.run(['systemctl','--user','show',unit,'--property=LoadState',
        '--property=ActiveState','--property=ControlGroup','--property=InvocationID'],
        capture_output=True,text=True,timeout=10)
    fields=dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)
    if fields.get('LoadState')=='not-found': return fields
    if r.returncode or fields.get('LoadState')!='loaded' or not fields.get('ControlGroup'):
        raise OwnershipError('Cannot verify owned run scope')
    return fields


def own_booking(intent):
    import psutil
    fields=scope_state(intent['unit'])
    group=Path('/proc/self/cgroup').read_text().strip().split('0::')[-1]
    if fields.get('ControlGroup')!=intent['expected_cgroup'] or group!=intent['expected_cgroup']:
        raise OwnershipError('Native worker cgroup differs from durable intent')
    return {'pid':os.getpid(),'start_time':psutil.Process().create_time(),
            'cgroup':group,'invocation_id':fields['InvocationID']}


def _identity(fields,intent):
    if fields.get('LoadState')=='not-found': return
    if fields.get('ControlGroup')!=intent['expected_cgroup']:
        raise OwnershipError('Loaded scope identity differs from durable intent')
    booking=intent.get('booking')
    if booking and fields.get('InvocationID')!=booking['invocation_id']:
        raise OwnershipError('Loaded scope invocation identity differs from booking')


def _empty(fields,intent):
    _identity(fields,intent)
    if fields.get('LoadState')=='not-found': return True
    events=Path('/sys/fs/cgroup')/intent['expected_cgroup'].lstrip('/')/'cgroup.events'
    try: values=dict(line.split() for line in events.read_text().splitlines())
    except OSError as exc: raise OwnershipError('Cannot prove run cgroup emptiness') from exc
    return values.get('populated')=='0'


def _stop_snapshot(intent):
    fields=scope_state(intent['unit']); _identity(fields,intent)
    if fields.get('LoadState')=='not-found': return []
    freeze=subprocess.run(['systemctl','--user','freeze',intent['unit']],capture_output=True,timeout=10)
    fields=scope_state(intent['unit']); _identity(fields,intent)
    if fields.get('LoadState')=='not-found': return []
    if freeze.returncode: raise OwnershipError('Cannot freeze run scope before snapshot')
    base=Path('/sys/fs/cgroup')/intent['expected_cgroup'].lstrip('/')
    import psutil
    observed=[]
    # Every nested cgroup, not just the root. No argv/environment scan.
    try:
        files=[base/'cgroup.procs',*base.glob('**/cgroup.procs')]
        pids={int(p) for file in files for p in file.read_text().split()}
        if len(pids)>4096: raise OwnershipError('Run scope snapshot exceeds bound')
        for pid in sorted(pids):
            try:
                process=psutil.Process(pid)
                observed.append({'pid':pid,'comm':process.name()[:64],'start_time':process.create_time()})
            except psutil.NoSuchProcess: continue
            except (psutil.Error,OSError):
                observed.append({'pid':pid,'comm':'unknown','start_time':None})
    except OSError as exc: raise OwnershipError('Cannot snapshot frozen run cgroup') from exc
    subprocess.run(['systemctl','--user','kill','--signal=SIGKILL',intent['unit']],capture_output=True,timeout=10)
    subprocess.run(['systemctl','--user','stop',intent['unit']],capture_output=True,timeout=15)
    if not _empty(scope_state(intent['unit']),intent):
        raise OwnershipError('Owned scope still populated after kill/stop')
    return observed


def close_scope(intent,run,run_dir):
    validate_intent(intent,run,run_dir)
    if intent['boot_id']!=boot_id():
        return {'contained':True,'status':'prior-boot','observed':[],'unknown':[]}
    admission=Path(intent['admission']); admission.unlink(missing_ok=True)
    gate=Path(intent['launch_gate']); gate.parent.mkdir(parents=True,exist_ok=True)
    observed=_stop_snapshot(intent)
    deadline=time.monotonic()+20
    with gate.open('a+') as lock:
        while True:
            try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB); break
            except BlockingIOError:
                observed.extend(_stop_snapshot(intent))
                if time.monotonic()>deadline: raise OwnershipError('Run scope launcher has not quiesced')
                time.sleep(.05)
        observed.extend(_stop_snapshot(intent))
        if not _empty(scope_state(intent['unit']),intent):
            raise OwnershipError('Run scope containment could not be verified')
    # Worker-disposed verified resources should already be absent. Every
    # remaining frozen process is unknown, not permission to publish after kill.
    return {'contained':True,'status':'stopped' if intent.get('booking') else 'launch-unconfirmed',
            'observed':observed,'unknown':observed}


def launch_argv(intent, argv, runtime):
    Path(intent['launch_gate']).touch(mode=0o600,exist_ok=True)
    Path(intent['admission']).touch(mode=0o600,exist_ok=False)
    import shlex
    launch=['systemd-run','--user','--scope','--collect','--quiet',f'--unit={intent["unit"]}',
            f'--property=RuntimeMaxSec={runtime:g}','--property=TimeoutStopSec=5','--',*argv]
    guarded=f'test -f {shlex.quote(intent["admission"])} || exit 125; exec {shlex.join(launch)}'
    return ['flock','--shared','--close',intent['launch_gate'],'/bin/sh','-c',guarded]
