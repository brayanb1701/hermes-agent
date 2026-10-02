"""Bounded lock contention is durable deferral, never completed work."""
import json
from pathlib import Path
import pytest
from test_vault_ownership import contract,write_contract,init_repo,RUNNER,load_module


def test_wait_expiry_defers_then_next_dispatch_executes(tmp_path,monkeypatch):
    repo,remote=init_repo(tmp_path); cfg=contract(tmp_path/'home',repo=repo)
    cfg['remote']=str(remote); cfg['owner_lock_wait_seconds']=1
    write_contract(Path(cfg['hermes_home']),cfg)
    runner=load_module(RUNNER,'contention_runner')
    from vault_ownership_common import owner_lock
    called=[]
    def execute(job,root,directory):
        called.append(True); (root/'notes').mkdir(); (root/'notes/out.md').write_text('later work'); return 'ran'
    job={'id':'deferred-test','ownership_timeout':30,'allowed_paths':['notes/']}
    with owner_lock(cfg):
        result=runner.execute_job(cfg,job,executor=execute)
    assert result['status']=='deferred' and result['executed'] is False
    assert called==[] and not (Path(cfg['state_dir'])/'pending-owner.json').exists()
    ledger=json.loads(max((Path(cfg['state_dir'])/'dispatch-outcomes').glob('deferred-test-*.json'),key=lambda p:p.stat().st_mtime).read_text())
    assert ledger['status']=='deferred' and ledger['executed'] is False
    assert runner.execute_job(cfg,job,executor=execute)=='ran'
    ledger=json.loads(max((Path(cfg['state_dir'])/'dispatch-outcomes').glob('deferred-test-*.json'),key=lambda p:p.stat().st_mtime).read_text())
    assert ledger['status']=='executed' and ledger['executed'] is True


def test_budget_refuses_before_marker(tmp_path):
    repo,remote=init_repo(tmp_path); cfg=contract(tmp_path/'home',repo=repo);cfg['remote']=str(remote)
    write_contract(Path(cfg['hermes_home']),cfg)
    runner=load_module(RUNNER,'budget_runner')
    with pytest.raises(runner.OwnershipError,match='budget'):
        runner.execute_job(cfg,{'id':'over-budget','ownership_timeout':3550},executor=lambda *a:pytest.fail('cannot execute'))
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()
