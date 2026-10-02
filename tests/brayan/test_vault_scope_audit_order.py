"""V2 worker leaves unknown processes for wrapper freeze/snapshot/kill."""
import json,os,subprocess,sys
from pathlib import Path
import pytest
from test_vault_ownership import RUNNER,load_module


def test_v2_worker_records_unknown_child_without_killing_before_freeze(tmp_path,monkeypatch):
    runner=load_module(RUNNER,'scope_audit_order_runner')
    import cron.scheduler
    from types import SimpleNamespace
    monkeypatch.setattr(runner.sys,'platform','linux')
    monkeypatch.setattr(__import__('ctypes'),'CDLL',lambda *a,**k:SimpleNamespace(prctl=lambda *a:0))
    state=tmp_path/'state';directory=state/'runs'/('c'*32);directory.mkdir(parents=True)
    payload=directory/'job.json';payload.write_text('{}')
    (state/'pending-owner.json').write_text(json.dumps({'version':2,'phase':'executing','containment':{'expected_cgroup':'/simulated'}}))
    booking={'pid':os.getpid(),'start_time':1.0,'cgroup':'/simulated','invocation_id':'d'*32}
    monkeypatch.setattr(runner,'own_booking',lambda *a:booking)
    monkeypatch.setattr(runner,'_shutdown_native_kernels',lambda:{'local':'ok','remote':'ok'})
    runtime=tmp_path/'ipc';runtime.mkdir();monkeypatch.setenv('BH_RUNTIME_DIR',str(runtime))
    process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'])
    monkeypatch.setattr(cron.scheduler,'run_job',lambda job:(True,'document','response',None))
    try:
        code=runner._native_worker(payload,directory/'result.json')
        assert code==1 and process.poll() is None, 'Worker killed unknown child before frozen scope evidence'
        receipt=json.loads((directory/'result.json').read_text())
        assert receipt['success'] is False and receipt['descendant_cleanup']['deferred_to_scope'] is True
        assert receipt['descendant_cleanup']['survivor_count']>0
    finally:
        if process.poll() is None:process.kill()
        process.wait(timeout=5)
