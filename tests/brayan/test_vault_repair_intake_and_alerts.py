"""T3-T6 behavior, isolated real Git and atomic journal fault subprocesses."""
import json,os,signal,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_vault_native_intake import setup,PLUGIN
from test_vault_ownership import RUNNER,load_module,contract
from test_vault_owner_recovery import runner
from test_vault_review_repairs import v2_state,unchanged


def tree_state(runner,cfg,repo,remote):
    pending=Path(cfg['state_dir'])/'pending-owner.json'
    return (runner.git(repo,'rev-parse','HEAD'),runner.git(remote,'rev-parse','main'),pending.read_bytes(),
            runner.git(repo,'status','--porcelain=v1','-uall'),
            {str(p.relative_to(repo)):p.read_bytes() for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts})


@pytest.mark.parametrize('case',['clean','unit-populated','committed-not-pushed','trusted-published','dirty','moved','wrong-branch','bad-trailer','wrong-session','wrong-capture','unknown'])
def test_T3_intake_recognition_and_terminal_population(tmp_path,runner,monkeypatch,case):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    marker=plugin._begin(cfg,event,'session')
    pending=Path(cfg['state_dir'])/'pending-owner.json'
    if case=='unit-populated':
        import vault_run_scope as scopes
        monkeypatch.setattr(scopes,'CGROUP_ROOT',tmp_path/'cgroup-data')
        unit='vault-intake-'+marker['terminal_id']+'-'+'c'*32+'.scope';marker['terminal_units']=[unit]
        group=f'/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice/{unit}'
        target=scopes.CGROUP_ROOT/group.lstrip('/');target.mkdir(parents=True);(target/'cgroup.events').write_text('populated 1\n')
        monkeypatch.setattr(scopes,'scope_state',lambda name:dict(LoadState='loaded',ActiveState='active',ControlGroup=group))
    elif case=='dirty':(repo/'raw.bin').write_bytes(b'raw\x00\xff')
    elif case=='wrong-branch':runner.git(repo,'checkout','-b','wrong')
    elif case=='unknown':marker['unrecognized']=True
    elif case in {'committed-not-pushed','trusted-published','bad-trailer','wrong-session','wrong-capture','moved'}:
        (repo/'inbox').mkdir();(repo/'inbox/raw.bin').write_bytes(b'raw\x00\xff')
        runner.git(repo,'add','.')
        message='Capture\n\nSession: '+marker['id']+'\nCapture-ID: '+marker['message_id']+'\nBase-SHA: '+marker['base']
        if case=='bad-trailer':message+='\nSession: '+marker['id']
        if case=='wrong-session':message=message.replace('Session: '+marker['id'],'Session: '+'f'*32)
        if case=='wrong-capture':message=message.replace('Capture-ID: '+marker['message_id'],'Capture-ID: other-capture')
        runner.git(repo,'commit','-m',message)
        if case!='moved':marker['phase']='published' if case in {'trusted-published','bad-trailer','wrong-session','wrong-capture'} else 'committed'
        if case in {'trusted-published','bad-trailer','wrong-session','wrong-capture'}:runner.git(repo,'push',str(remote),'HEAD:main')
    pending.write_text(json.dumps(marker));before=tree_state(runner,cfg,repo,remote)
    if case in {'clean','trusted-published'}:
        assert runner.reconcile_pending(cfg,marker['id'])['status']=='intake-cleared'
        assert not pending.exists()
        assert runner.git(repo,'rev-parse','HEAD')==before[0] and runner.git(remote,'rev-parse','main')==before[1]
    else:
        with pytest.raises(runner.OwnershipError):runner.reconcile_pending(cfg,marker['id'])
        assert tree_state(runner,cfg,repo,remote)==before
        assert not (Path(cfg['state_dir'])/'failed').exists()


@pytest.mark.platforms('linux')
@pytest.mark.parametrize('window',['before-replace','after-replace'])
def test_T4_atomic_journal_crash_is_complete_old_or_new(tmp_path,runner,monkeypatch,window):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    old=plugin._begin(cfg,event,'old-session');new=dict(old,session_key='new-session')
    pending=Path(cfg['state_dir'])/'pending-owner.json';base=runner.git(repo,'rev-parse','HEAD')
    code='''import json,os,signal,sys
from pathlib import Path
import vault_ownership as r
pending=Path(sys.argv[1]);new=json.loads(sys.argv[2]);window=sys.argv[3]
original=os.replace
def fault(src,dst):
 if Path(dst)==pending:
  if window=='before-replace':os.kill(os.getpid(),signal.SIGKILL)
  original(src,dst)
  os.kill(os.getpid(),signal.SIGKILL)
 else:original(src,dst)
os.replace=fault
r._atomic_write_json(pending,new)
'''
    from test_vault_ownership import SCRIPTS,ROOT
    result=subprocess.run([sys.executable,'-c',code,str(pending),json.dumps(new),window],env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(SCRIPTS),str(ROOT)])),capture_output=True,timeout=15)
    assert result.returncode==-signal.SIGKILL,result.stderr
    assert json.loads(pending.read_text())==(old if window=='before-replace' else new)
    assert runner.git(repo,'rev-parse','HEAD')==base==runner.git(remote,'rev-parse','main')
    assert runner.reconcile_pending(cfg,old['id'])['status']=='intake-cleared'


def test_T5_prepublication_abandon_archives_bytes_then_next_job(tmp_path,runner,monkeypatch):
    cfg,repo,remote,state,root,directory,run,marker=v2_state(tmp_path,runner,'executing')
    (root/'changed.txt').write_bytes(b'never publish\x00\xff')
    (directory/'result.json').unlink()
    monkeypatch.setattr(runner,'_close_run_scope',lambda *a:{'contained':True,'unknown':[],'observed':[]})
    base=runner.git(repo,'rev-parse','HEAD')
    result=runner.abandon_incomplete(cfg,run)
    assert result['status']=='archived'
    assert (Path(result['archive'])/'files/changed.txt').read_bytes()==b'never publish\x00\xff'
    assert not (directory/'result.json').exists() and not (state/'pending-owner.json').exists()
    assert runner.git(repo,'rev-parse','HEAD')==base==runner.git(remote,'rev-parse','main')
    def work(j,r,d): (r/'next.txt').write_text('clean next job');return 'next ran'
    assert runner.execute_job(cfg,dict(id='next-job',allowed_paths=['next.txt'],ownership_timeout=30),executor=work)=='next ran'
    assert (repo/'next.txt').read_text()=='clean next job'
    assert not (repo/'changed.txt').exists()
    assert runner.git(repo,'rev-parse','HEAD')==runner.git(remote,'rev-parse','main')!=base


@pytest.mark.platforms('linux')
def test_T6_owner_sync_intake_suppress_one_incident_with_durable_events(tmp_path,runner,monkeypatch):
    cfg,repo,remote,state,root,directory,run,marker=v2_state(tmp_path,runner)
    cfg['vault_path']=str(repo);cfg['intake_allowed_paths']=['inbox/']
    import vault_run_scope as scopes
    monkeypatch.setattr(scopes,'CGROUP_ROOT',tmp_path/'cgroup-data')
    group=scopes.CGROUP_ROOT/marker['containment']['expected_cgroup'].lstrip('/');group.mkdir(parents=True)
    (group/'cgroup.events').write_text('populated 1\nfrozen 1\n');(group/'cgroup.procs').write_text('')
    monkeypatch.setattr(scopes,'scope_state',lambda unit:dict(LoadState='loaded',ActiveState='active',ControlGroup=marker['containment']['expected_cgroup'],InvocationID='b'*32))
    monkeypatch.setattr(scopes,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout='')))
    # Budgeted entry point still takes the real lock and invokes shared reconciliation.
    before=unchanged(runner,cfg,repo,remote,state,root)
    with pytest.raises(runner.OwnershipError,match='still populated'):
        runner.execute_job(cfg,dict(id='first-job',allowed_paths=['next.txt'],ownership_timeout=30),executor=lambda *a:pytest.fail('blocked work executed'))
    outcome=runner.execute_job(cfg,dict(id='suppressed-job',allowed_paths=['next.txt'],ownership_timeout=30),executor=lambda *a:pytest.fail('blocked work executed'))
    assert outcome['status']=='blocked' and outcome['executed'] is False and outcome['wakeAgent'] is False
    import vault_contributions as vc
    sync=vc.process_pending_reviews(cfg,runner=lambda *a:pytest.fail('suppressed sync contacted remote API'))
    assert sync['status']=='blocked' and sync['executed'] is False and sync['wakeAgent'] is False
    plugin=load_module(PLUGIN,'repair_intake_alert_plugin')
    with pytest.raises(runner.OwnershipError):plugin._begin(cfg,SimpleNamespace(message_id='capture'),'next-session')
    assert unchanged(runner,cfg,repo,remote,state,root)==before
    alerts=[json.loads(p.read_text()) for p in (state/'incident-alerts').glob('*.json')]
    events=[json.loads(p.read_text()) for p in (state/'dispatch-outcomes').glob('*.json')]
    assert len(alerts)==1 and alerts[0]['alert']=='admitted-not-delivery-confirmed'
    assert len(events)==4
    assert {e['job'] for e in events}=={'first-job','suppressed-job','contributions-sync','native-intake'}
    assert all(e['status']=='blocked' and e['executed'] is False and e['run']==run for e in events)
    assert len({e['reason_digest'] for e in events})==1




@pytest.mark.parametrize('variant',['valid','wrong-message','outside-scope'])
def test_T4_committing_promotion_checks_actual_wrapper_commit(tmp_path,runner,monkeypatch,variant):
    cfg,repo,remote,state,root,directory,run,marker=v2_state(tmp_path,runner,'committing',True)
    (directory/'job.json').write_text(json.dumps({'id':marker['job']}))
    if variant=='outside-scope':(root/'outside.txt').write_text('not authorized')
    runner.git(root,'add','.')
    message=runner._owner_commit_message(marker['job'],cfg,run,marker['base']) if variant!='wrong-message' else 'untrusted commit'
    runner.git(root,'commit','-m',message);head=runner.git(root,'rev-parse','HEAD')
    monkeypatch.setattr(runner,'_close_run_scope',lambda *a:{'contained':True,'unknown':[],'observed':[]})
    before=(runner.git(repo,'rev-parse','HEAD'),runner.git(remote,'rev-parse','main'),(root/'changed.txt').read_bytes())
    if variant=='valid':
        assert runner.reconcile_pending(cfg,run)['status']=='recovered'
        assert runner.git(repo,'rev-parse','HEAD')==head==runner.git(remote,'rev-parse','main')
        assert not (state/'pending-owner.json').exists()
    else:
        with pytest.raises(runner.OwnershipError):runner.reconcile_pending(cfg,run)
        assert (runner.git(repo,'rev-parse','HEAD'),runner.git(remote,'rev-parse','main'),(root/'changed.txt').read_bytes())==before
        assert (state/'pending-owner.json').exists()


def test_T3_atomic_phase_replace_failure_retains_previous_json(tmp_path,runner,monkeypatch):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    old=plugin._begin(cfg,event,'session');pending=Path(cfg['state_dir'])/'pending-owner.json'
    original=runner.os.replace
    def fail(src,dst):
        if Path(dst)==pending:raise OSError('injected atomic replace failure')
        return original(src,dst)
    monkeypatch.setattr(runner.os,'replace',fail)
    with pytest.raises(OSError,match='atomic replace'):runner._marker_phase(pending,old,'committed')
    assert json.loads(pending.read_text())==old
    assert runner.git(repo,'rev-parse','HEAD')==old['base']==runner.git(remote,'rev-parse','main')


@pytest.mark.asyncio
async def test_T6_exact_dirty_reason_change_and_recoverable_sync_sequence(tmp_path,runner,monkeypatch):
    import vault_run_scope as scopes, vault_incident_alerts as alerts, vault_contributions as vc
    from gateway.turn_scope import TurnScopeError
    cfg,repo,remote,state,root,directory,run,marker=v2_state(tmp_path,runner,'validating')
    cfg.update(vault_path=str(repo),intake_allowed_paths=['inbox/'])
    from test_vault_ownership import write_contract
    write_contract(Path(cfg['hermes_home']),cfg);monkeypatch.setenv('HERMES_HOME',cfg['hermes_home'])
    monkeypatch.setattr(scopes,'subprocess',SimpleNamespace(run=lambda *a,**k:SimpleNamespace(returncode=0,stdout='LoadState=not-found\n')))
    calls=[];original=alerts.admit_alert
    def counted(*a):
        admitted=original(*a);calls.append({'run':a[1],'reason':a[2],'admitted':admitted});return admitted
    monkeypatch.setattr(alerts,'admit_alert',counted)
    listed=[];monkeypatch.setattr(vc,'list_pending_reviews',lambda c,**k:listed.append(c) or [])
    plugin=load_module(PLUGIN,'exact_repair_intake_plugin')
    event=SimpleNamespace(source=SimpleNamespace(chat_id='inbox',platform=SimpleNamespace(value='telegram')),message_id='capture',_gateway_turn_result={'completed':True},_gateway_turn_error=None)
    gateway=SimpleNamespace(_effective_busy_input_mode=lambda source:'queue')
    monkeypatch.setattr('gateway.notes_intake.is_anything_inbox_source',lambda source:True)
    (repo/'README.md').write_text('unrelated dirty canonical')
    job=dict(id='reason-job',allowed_paths=['next.txt'],ownership_timeout=30)
    no_execution=lambda *a:pytest.fail('ambiguous work executed')
    with pytest.raises(runner.OwnershipError,match='Canonical'):runner.execute_job(cfg,job,executor=no_execution)
    assert vc.process_pending_reviews(cfg)['executed'] is False
    with pytest.raises(TurnScopeError,match='recovery'):
        async with plugin.turn_scope(event=event,source=event.source,session_key='next',gateway=gateway):pytest.fail('intake began')
    assert runner.execute_job(cfg,job,executor=no_execution)['wakeAgent'] is False
    assert vc.process_pending_reviews(cfg)['wakeAgent'] is False
    assert len(calls)==5 and sum(c['admitted'] for c in calls)==1 and listed==[]
    assert (root/'changed.txt').read_bytes()==b'failed evidence\n'
    assert (repo/'README.md').read_text()=='unrelated dirty canonical'
    (repo/'README.md').write_text('base\n')
    outside=tmp_path/'outside';runner.git(tmp_path,'clone','--branch','main',str(remote),str(outside));runner.git(outside,'config','user.name','Test');runner.git(outside,'config','user.email','test@example.invalid')
    (outside/'outside.txt').write_text('outside');runner.git(outside,'add','.');runner.git(outside,'commit','-m','outside');runner.git(outside,'push','origin','main')
    outside_head=runner.git(remote,'rev-parse','main')
    with pytest.raises(runner.OwnershipError,match='Published branch'):runner.execute_job(cfg,job,executor=no_execution)
    assert len(calls)==6 and sum(c['admitted'] for c in calls)==2
    assert len({c['reason'] for c in calls})==2
    assert (state/'pending-owner.json').exists() and not (state/'failed').exists()
    assert runner.git(remote,'rev-parse','main')==outside_head
    outcomes=[json.loads(p.read_text()) for p in (state/'dispatch-outcomes').glob('*.json')]
    assert len(outcomes)==6 and all(o['status']=='blocked' and o['executed'] is False and o['run']==run for o in outcomes)
    assert len({o['reason_digest'] for o in outcomes})==2
    recover=tmp_path/'recoverable';recover.mkdir()
    clean,canonical,bare,fresh,work,d,identity,m=v2_state(recover,runner,'executing')
    (d/'result.json').unlink()
    assert vc.process_pending_reviews(clean)['processed']==[]
    assert not (fresh/'pending-owner.json').exists() and (fresh/'failed'/identity/'files/changed.txt').read_bytes()==b'failed evidence\n'
    def execute(j,r,d):(r/'next.txt').write_text('normal next run');return 'ran normally'
    assert runner.execute_job(clean,job,executor=execute)=='ran normally'
    assert (canonical/'next.txt').read_text()=='normal next run' and runner.git(canonical,'rev-parse','HEAD')==runner.git(bare,'rev-parse','main')


def test_R2_event_pruning_retains_newest_256(tmp_path,runner):
    cfg=contract(tmp_path/'home')
    for i in range(260):runner._dispatch_outcome(cfg,'job','deferred',ordinal=i)
    values=[json.loads(p.read_text()) for p in (Path(cfg['state_dir'])/'dispatch-outcomes').glob('*.json')]
    assert len(values)==256 and {v['ordinal'] for v in values}==set(range(4,260))
