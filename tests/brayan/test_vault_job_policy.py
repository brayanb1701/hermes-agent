"""Role install/export invariants, preserving actual native schedule state."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from test_vault_ownership import contract, load_module, ROOT, SCRIPTS


def policy():
    return load_module(SCRIPTS / 'vault_job_policy.py', 'vault_job_policy')


def test_role_reconcile_exports_original_and_never_revives_consumed_jobs(tmp_path):
    p = policy()
    cfg = contract(tmp_path / 'hermes')
    cfg['managed_jobs'] = {'personal': {'allowed_paths': ['inbox/']}, 'once': {'allowed_paths': ['reviews/']}}
    cfg['host_job_ids'] = ['ci']
    original = dict(id='personal', prompt='original', script='gate.py', no_agent=False,
                    enabled=True, model='model', skills=['skill'], enabled_toolsets=['file'],
                    schedule={'kind':'cron','expr':'0 9 * * *'}, deliver='telegram:test',
                    repeat={'times':None,'completed':7}, next_run_at='future')
    once = dict(original, id='once', enabled=False, state='completed', repeat={'times':1,'completed':1})
    local = {'jobs':[original, once, dict(id='local',enabled=True), dict(id='ci',enabled=True,script='local_ci.py')]}
    bundle = {'jobs':[dict(original, model='new-model'), dict(once,enabled=True,repeat={'times':1,'completed':0}),dict(id='ci',script='foreign_ci.py')]}
    live, saved = p.reconcile(cfg, bundle, local, {'jobs':[]})
    wrapped = next(j for j in live['jobs'] if j['id']=='personal')
    assert wrapped['script']=='vault_ownership.py' and wrapped['no_agent']
    for key in ('schedule','deliver','repeat','next_run_at','enabled'):
        assert wrapped[key]==original[key]
    assert next(j for j in live['jobs'] if j['id']=='once')['enabled'] is False
    assert next(j for j in live['jobs'] if j['id']=='ci')['script']=='local_ci.py'
    exported = p.export_jobs(cfg, live, saved)
    assert next(j for j in exported['jobs'] if j['id']=='personal')['script']=='gate.py'
    assert not any(j['id']=='once' for j in exported['jobs'])
    assert next(j for j in saved['jobs'] if j['id']=='personal')['enabled_toolsets']==['file']
    cfg['role']='contributor'
    contributor, _ = p.reconcile(cfg,bundle,live,saved)
    assert not any(j.get('enabled') for j in contributor['jobs'] if j['id'] in cfg['managed_jobs'])
    assert next(j for j in contributor['jobs'] if j['id']=='local')['enabled']


def test_apply_and_sync_refuse_missing_contract_before_any_write(tmp_path, monkeypatch):
    for filename in ('apply-brayan-personalization.py', 'sync-brayan-personalization.py'):
        mod=load_module(ROOT/'scripts'/filename, filename.replace('-', '_'))
        home=tmp_path/filename/'home'
        bundle=tmp_path/filename/'bundle'
        bundle.mkdir(parents=True)
        monkeypatch.setattr(mod,'BUNDLE',bundle)
        if filename.startswith('apply'):
            monkeypatch.setattr(sys,'argv',[filename,'--hermes-home',str(home),'--apply'])
            with pytest.raises(Exception,match='contract'):
                mod.main()
        else:
            with pytest.raises(Exception,match='contract'):
                mod.sync(home)
        assert not home.exists()
        assert list(bundle.iterdir())==[]


@pytest.mark.parametrize('role', ['owner', 'contributor'])
def test_real_apply_reconciles_jobs_and_native_intake_config(tmp_path, monkeypatch, role):
    from test_vault_ownership import write_contract
    import yaml
    mod=load_module(ROOT/'scripts/apply-brayan-personalization.py','apply_role')
    home=tmp_path/'home'
    cfg=contract(home,role=role)
    if role=='contributor': cfg['owner_hostname']='OtherOwner'
    cfg.update(managed_jobs={'personal': {'allowed_paths':['inbox/']}},host_job_ids=[])
    write_contract(home,cfg)
    (home/'config.yaml').write_text(yaml.safe_dump({'notes_intake':{'enabled':True,'vision_model':'keep'}}))
    (home/'cron').mkdir()
    (home/'cron/jobs.json').write_text(json.dumps({'jobs':[dict(id='personal',enabled=True,script='gate.py',no_agent=False,deliver='local',schedule={'kind':'cron','expr':'0 9 * * *'})]}))
    bundle=tmp_path/'bundle'
    (bundle/'cron').mkdir(parents=True)
    (bundle/'cron/jobs.json').write_text(json.dumps({'jobs':[dict(id='personal',enabled=True,script='foreign.py')]}))
    monkeypatch.setattr(mod,'BUNDLE',bundle)
    monkeypatch.setattr(mod,'REPO',tmp_path)
    monkeypatch.setattr(mod,'COPY_DIRS',[])
    monkeypatch.setattr(sys,'argv',['apply','--hermes-home',str(home),'--apply','--preserve-config'])
    mod.main()
    result=json.loads((home/'cron/jobs.json').read_text())['jobs'][0]
    assert result['enabled']==(role=='owner')
    assert result['script']==('vault_ownership.py' if role=='owner' else 'gate.py')
    saved=json.loads((Path(cfg['state_dir'])/'jobs-original.json').read_text())['jobs'][0]
    assert saved['script']=='gate.py'
    conf=yaml.safe_load((home/'config.yaml').read_text())
    assert conf['notes_intake']['enabled']==(role=='owner')
    assert conf['notes_intake']['vision_model']=='keep'
    assert conf['updates']['branch']==cfg['maintenance_branch']


def test_shared_ownership_maintenance_stays_native_on_both_roles(tmp_path):
    p=policy()
    maintenance=dict(id='ownership-sync',name='darwin-vault-ownership-sync',script='vault_contributions.py',no_agent=True,enabled=True)
    for role in ('owner','contributor'):
        cfg=contract(tmp_path/'h',role=role)
        cfg.update(managed_jobs={},host_job_ids=[])
        jobs,originals=p.reconcile(cfg,{'jobs':[maintenance]},{'jobs':[]},{'jobs':[]})
        assert jobs['jobs']==[maintenance]
        assert p.export_jobs(cfg,jobs,originals)['jobs'][0]['script']=='vault_contributions.py'


def test_fresh_install_skips_one_shots_and_unknown_bundle_jobs_fail(tmp_path):
    p=policy()
    cfg=contract(tmp_path/'h')
    cfg['managed_jobs']={'one': {'allowed_paths':['inbox/']}}
    cfg['host_job_ids']=[]
    live,saved=p.reconcile(cfg, {'jobs':[dict(id='one',enabled=True,schedule={'kind':'once'})]}, {'jobs':[]}, {'jobs':[]})
    assert live['jobs']==[]
    with pytest.raises(Exception,match='classif'):
        p.reconcile(cfg, {'jobs':[dict(id='unknown')]}, {'jobs':[]}, {'jobs':[]})
