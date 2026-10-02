"""Bounded Opus repair T1-T6: real Git/processes, controller fixtures as data."""
import json,os,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_vault_owner_recovery import failed_state,runner
from test_vault_ownership import RUNNER,load_module


def v2_state(tmp_path,runner,phase='executing',success=False):
    cfg,repo,remote,state,root,directory,run,marker=failed_state(tmp_path,runner,phase=phase)
    from vault_run_scope import scope_intent
    intent=scope_intent(run,directory);intent['booking']={'pid':os.getpid(),'start_time':1.0,'cgroup':intent['expected_cgroup'],'invocation_id':'b'*32}
    proof={'contained':True,'unknown':[],'observed':[]}
    marker.update(version=2,containment=intent,containment_proof=proof)
    receipt={'version':2,'success':success,'error':None if success else 'fixture failure','launch':intent['booking'],'kernel_cleanup':{'local':'ok','remote':'ok'},'descendant_cleanup':{'observed':[],'live_count':0,'survivor_count':0,'survivors':[]},'resource_cleanup':{'browser':{'ok':True,'daemons':[],'extra_tabs':'unverified'}}}
    (directory/'result.json').write_text(json.dumps(receipt));(state/'pending-owner.json').write_text(json.dumps(marker))
    cfg['managed_jobs']={marker['job']:{'allowed_paths':marker['intent']['allowed_paths']}}
    return cfg,repo,remote,state,root,directory,run,marker


def unchanged(runner,cfg,repo,remote,state,root):
    return runner.git(repo,'rev-parse','HEAD'),runner.git(remote,'rev-parse','main'),(root/'changed.txt').read_bytes(),(state/'pending-owner.json').read_bytes()


@pytest.mark.platforms('linux')
def test_T1_populated_data_cgroup_blocks_two_reconciles(tmp_path,runner,monkeypatch):
    cfg,repo,remote,state,root,directory,run,marker=v2_state(tmp_path,runner,'publishing',True)
    marker['head']=marker['base'];(state/'pending-owner.json').write_text(json.dumps(marker))
    import vault_run_scope as scopes
    monkeypatch.setattr(scopes,'CGROUP_ROOT',tmp_path/'cgroup-data')
    group=scopes.CGROUP_ROOT/marker['containment']['expected_cgroup'].lstrip('/');group.mkdir(parents=True)
    process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(15)'])
    (group/'cgroup.events').write_text('populated 1\nfrozen 1\n');(group/'cgroup.procs').write_text(str(process.pid))
    fields={'LoadState':'loaded','ActiveState':'active','ControlGroup':marker['containment']['expected_cgroup'],'InvocationID':'b'*32}
    monkeypatch.setattr(scopes,'scope_state',lambda unit:fields)
    monkeypatch.setattr(scopes,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout='')))
    # The controller is data; real Git must retain its real subprocess runner.
    original_git=runner.git
    monkeypatch.setattr(runner,'_root_aware_processes',lambda *a,**k:pytest.fail('V2 must not globally inspect processes'))
    # Git subprocess calls are unnecessary before the populated scope refuses.
    baseline=((root/'changed.txt').read_bytes(),(state/'pending-owner.json').read_bytes())
    import vault_incident_alerts as alerts
    try:
        with pytest.raises(runner.OwnershipError,match='still populated'):alerts.reconcile_for_writer(cfg)
        with pytest.raises(alerts.RepeatedIncident,match='still populated'):alerts.reconcile_for_writer(cfg)
        assert ((root/'changed.txt').read_bytes(),(state/'pending-owner.json').read_bytes())==baseline
        assert not (state/'failed').exists() and process.poll() is None
        assert len(list((state/'incident-alerts').glob('*.json')))==1
    finally:process.kill();process.wait(timeout=5)
    monkeypatch.undo()
    assert original_git(repo,'rev-parse','HEAD')==marker['base']==original_git(remote,'rev-parse','main')


@pytest.mark.parametrize('mutation',['receipt-commit','receipt-head','agent-commit','validating-outside'])
def test_T2_v2_ambiguous_prepublication_preserves_everything(tmp_path,runner,monkeypatch,mutation):
    cfg,repo,remote,state,root,directory,run,marker=v2_state(tmp_path,runner)
    monkeypatch.setattr(runner,'_close_run_scope',lambda *a:{'contained':True,'unknown':[],'observed':[]})
    if mutation.startswith('receipt-'):
        receipt=json.loads((directory/'result.json').read_text());receipt[mutation.split('-')[1]]=marker['base'];(directory/'result.json').write_text(json.dumps(receipt))
    elif mutation=='agent-commit':runner.git(root,'add','.');runner.git(root,'commit','-m','agent commit')
    else:
        marker['phase']='validating';(state/'pending-owner.json').write_text(json.dumps(marker))
        outside=tmp_path/'outside';runner.git(tmp_path,'clone',str(remote),str(outside));runner.git(outside,'checkout','main');runner.git(outside,'config','user.name','Test');runner.git(outside,'config','user.email','test@example.invalid')
        (outside/'outside.md').write_text('outside');runner.git(outside,'add','.');runner.git(outside,'commit','-m','outside');runner.git(outside,'push','origin','main')
    before=unchanged(runner,cfg,repo,remote,state,root)
    with pytest.raises(runner.OwnershipError):runner.reconcile_pending(cfg,run)
    assert unchanged(runner,cfg,repo,remote,state,root)==before
    assert not (state/'failed').exists()


@pytest.mark.parametrize('phase',['committing','publishing','integrating'])
def test_T5_abandon_never_resumes_successful_publication(tmp_path,runner,monkeypatch,phase):
    cfg,repo,remote,state,root,directory,run,marker=v2_state(tmp_path,runner,phase,True)
    (directory/'job.json').write_text(json.dumps({'id':marker['job']}))
    runner.git(root,'add','.');runner.git(root,'commit','-m',runner._owner_commit_message(marker['job'],cfg,run,marker['base']))
    head=runner.git(root,'rev-parse','HEAD')
    if phase!='committing':marker['head']=head
    if phase=='integrating':
        runner.git(root,'push',str(remote),'HEAD:main');marker['remote_head']=head
    (state/'pending-owner.json').write_text(json.dumps(marker))
    monkeypatch.setattr(runner,'_close_run_scope',lambda *a:{'contained':True,'unknown':[],'observed':[]})
    before=unchanged(runner,cfg,repo,remote,state,root)
    with pytest.raises(runner.OwnershipError,match='abandon'):runner.abandon_incomplete(cfg,run)
    assert unchanged(runner,cfg,repo,remote,state,root)==before


def test_R2_executed_publication_failure_is_not_recorded_as_unexecuted_block(tmp_path,runner):
    from test_vault_ownership import init_repo,contract,write_contract
    repo,remote=init_repo(tmp_path);home=tmp_path/'home';cfg=contract(home,repo=repo);cfg['remote']=str(remote);write_contract(home,cfg)
    called=[]
    def agent_commit(job,root,directory):
        called.append(True);(root/'next.txt').write_text('work really executed')
        runner.git(root,'add','.');runner.git(root,'commit','-m','agent moved HEAD')
        return 'executed'
    with pytest.raises(runner.OwnershipError,match='changed HEAD'):
        runner.execute_job(cfg,dict(id='executed-failure',allowed_paths=['next.txt'],ownership_timeout=30),executor=agent_commit)
    assert called==[True] and (Path(cfg['state_dir'])/'pending-owner.json').exists()
    records=[json.loads(p.read_text()) for p in (Path(cfg['state_dir'])/'dispatch-outcomes').glob('*.json')]
    assert not any(r['job']=='executed-failure' and r['executed'] is False for r in records)


def test_R2_deferred_history_survives_executed_event(tmp_path,runner):
    from test_vault_ownership import contract
    cfg=contract(tmp_path/'home')
    runner._dispatch_outcome(cfg,'job','deferred',reason='busy')
    runner._dispatch_outcome(cfg,'job','executed')
    outcomes=[json.loads(p.read_text()) for p in (Path(cfg['state_dir'])/'dispatch-outcomes').glob('*.json')]
    assert sorted(o['status'] for o in outcomes)==['deferred','executed']
    assert [o['executed'] for o in outcomes if o['status']=='deferred']==[False]




def test_N1_snapshot_truncation_still_kills_and_stops_exact_scope(tmp_path,monkeypatch):
    load_module(RUNNER,'repair_bound_import');import vault_run_scope as scopes
    monkeypatch.setattr(scopes,'CGROUP_ROOT',tmp_path/'data')
    intent=scopes.scope_intent('d'*32,tmp_path)
    group=scopes.CGROUP_ROOT/intent['expected_cgroup'].lstrip('/');group.mkdir(parents=True)
    (group/'cgroup.procs').write_text(' '.join(str(900000000+i) for i in range(5000)))
    (group/'cgroup.events').write_text('populated 1\n')
    state={'LoadState':'loaded','ActiveState':'active','ControlGroup':intent['expected_cgroup']};commands=[]
    monkeypatch.setattr(scopes,'scope_state',lambda unit:dict(state))
    def control(argv,**kw):
        commands.append(argv)
        if 'kill' in argv:state.update(ActiveState='inactive',ControlGroup='')
        return SimpleNamespace(returncode=0,stdout='')
    monkeypatch.setattr(scopes,'subprocess',SimpleNamespace(run=control))
    proof=scopes.close_scope(intent,'d'*32,tmp_path)
    assert proof['contained'] and proof['unknown'][0]['total_count']==5000
    assert proof['unknown'][0]['evidence_limit']==4096
    assert any('kill' in c for c in commands) and any('stop' in c for c in commands)
    assert all(c[-1]==intent['unit'] for c in commands)


def test_N2_loaded_retired_empty_scope_is_verified_not_false_failure(tmp_path,monkeypatch):
    load_module(RUNNER,'repair_scope_imports');import vault_run_scope as scopes
    intent=scopes.scope_intent('a'*32,tmp_path)
    fields={'LoadState':'loaded','ActiveState':'inactive','ControlGroup':'','InvocationID':'b'*32}
    monkeypatch.setattr(scopes,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout='\n'.join(k+'='+v for k,v in fields.items()))))
    assert scopes.scope_state(intent['unit'])==fields
    assert scopes._empty(fields,intent) is True
    assert scopes.close_scope(intent,'a'*32,tmp_path)['contained'] is True
    fields['ActiveState']='active'
    with pytest.raises(scopes.OwnershipError):scopes.scope_state(intent['unit'])
