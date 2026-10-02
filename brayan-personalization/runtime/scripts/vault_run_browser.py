"""Dispose only positively identified run-local harness daemons.

IPC PID, durable birth fingerprint and cgroup must all agree before signaling.
Extra agent-created tabs are unknown hygiene, never closed by global target diff.
"""
import contextlib
import json
import os
from pathlib import Path
import re
import signal
import time


def _alive(pid, fingerprint, admin):
    import psutil
    try:
        process=psutil.Process(pid)
        return (admin._process_start_time(pid)==fingerprint
                and process.status() not in {psutil.STATUS_ZOMBIE,psutil.STATUS_DEAD})
    except psutil.NoSuchProcess: return False


def shutdown_browsers(intent):
    result={'ok':True,'daemons':[],'extra_tabs':'unverified'}
    runtime=Path(os.environ['BH_RUNTIME_DIR'])
    paths=list(runtime.glob('bu-*.pid'))+list(runtime.glob('bu-*.sock'))
    names={p.name[3:].rsplit('.',1)[0] for p in paths}
    if len(names)>32:
        return dict(result,ok=False,error='endpoint-bound')
    if not names: return result
    try:
        from browser_harness import _ipc as ipc, admin
    except ImportError:
        return dict(result,ok=False,error='harness-unavailable')
    for name in sorted(names):
        record={'name':name,'status':'unknown','identity':'unverified','tab_cleanup':'unverified'}
        result['daemons'].append(record)
        try:
            if not re.fullmatch('[A-Za-z0-9_-]{1,64}',name):
                raise ValueError('invalid-name')
            path=runtime/f'bu-{name}.pid'
            if path.is_symlink(): raise ValueError('symlink-endpoint')
            saved=json.loads(path.read_text())
            pid=saved if type(saved) is int else saved['pid']
            started=admin._process_start_time(pid)
            if type(pid) is not int or pid<=0 or started is None: raise ValueError('missing-fingerprint')
            sock,token=ipc.connect(name,timeout=3)
            with sock: ping=ipc.request(sock,token,{'meta':'ping'})
            group=Path(f'/proc/{pid}/cgroup').read_text().strip().split('0::')[-1]
            if (ping.get('pid')!=pid or admin._process_start_time(pid)!=started
                    or group!=intent['expected_cgroup']):
                raise ValueError('identity-mismatch')
            if ping.get('browser_kind')=='cloud':
                raise ValueError('unsupported-cloud-resource-cleanup')
            record.update(pid=pid,start_time=started,identity='verified')
            # Harness may escalate internally after an acknowledged shutdown;
            # do not claim cooperative-only cleanup just from this return value.
            try:
                admin.restart_daemon(name,require_clean=True)
                record['status']='shutdown-confirmed'
            except Exception as exc:
                record.update(status='forced',cooperative_error=type(exc).__name__)
            if _alive(pid,started,admin):
                group=Path(f'/proc/{pid}/cgroup').read_text().strip().split('0::')[-1]
                if group!=intent['expected_cgroup']: raise ValueError('identity-moved')
                if admin._process_start_time(pid)!=started: raise ValueError('identity-reused')
                os.kill(pid,signal.SIGKILL)
                record['status']='forced'
            deadline=time.monotonic()+5
            while _alive(pid,started,admin) and time.monotonic()<deadline: time.sleep(.05)
            if _alive(pid,started,admin): raise ValueError('daemon-still-live')
            record['daemon_exit']='verified'
        except Exception as exc:
            record.update(status='unknown',error=type(exc).__name__+':'+str(exc)[:80])
            result['ok']=False
    return result
