"""V2 phase table real Git archive evidence, intent-only never success."""
import json
from pathlib import Path
import pytest
from test_vault_owner_recovery import failed_state,runner


@pytest.mark.parametrize('phase',['prepared','executing','validating'])
def test_v2_missing_completion_quarantines_each_prepublication_phase(tmp_path,runner,monkeypatch,phase):
    cfg,repo,remote,state,root,run_dir,run,marker=failed_state(tmp_path,runner,phase=phase)
    from vault_run_scope import scope_intent
    marker.update(version=2,containment=scope_intent(run,run_dir))
    (run_dir/'result.json').unlink()
    (root/'changed.txt').write_bytes(b'raw\x00\xff\ndata')
    (state/'pending-owner.json').write_text(json.dumps(marker))
    monkeypatch.setattr(runner,'_close_run_scope',lambda *a:{'contained':True,'status':'launch-unconfirmed','observed':[],'unknown':[]})
    before=runner.git(remote,'rev-parse','main')
    result=runner.reconcile_pending(cfg,run)
    archive=Path(result['archive'])
    assert (archive/'files/changed.txt').read_bytes()==b'raw\x00\xff\ndata'
    assert runner.git(remote,'rev-parse','main')==before
    assert not (state/'pending-owner.json').exists()
    assert not (run_dir/'result.json').exists()
    manifest=json.loads((archive/'manifest.json').read_text())
    assert manifest['run']==run
    result=json.loads((archive/'incomplete-failure.json').read_text())
    assert result['status']=='incomplete-failure' and result['publication']=='never-authorized'


def test_v2_outside_push_is_recorded_only_in_executing_archive(tmp_path,runner,monkeypatch):
    cfg,repo,remote,state,root,run_dir,run,marker=failed_state(tmp_path,runner)
    from vault_run_scope import scope_intent
    marker.update(version=2,containment=scope_intent(run,run_dir));(run_dir/'result.json').unlink()
    (state/'pending-owner.json').write_text(json.dumps(marker))
    outside=tmp_path/'outside'; runner.git(tmp_path,'clone',str(remote),str(outside))
    runner.git(outside,'checkout','main');runner.git(outside,'config','user.name','Test');runner.git(outside,'config','user.email','test@example.invalid')
    (outside/'outside.md').write_text('outside');runner.git(outside,'add','.');runner.git(outside,'commit','-m','outside')
    runner.git(outside,'push','origin','main');head=runner.git(remote,'rev-parse','main')
    monkeypatch.setattr(runner,'_close_run_scope',lambda *a:{'contained':True,'status':'launch-unconfirmed','observed':[],'unknown':[]})
    result=runner.reconcile_pending(cfg,run)
    assert json.loads((Path(result['archive'])/'incomplete-failure.json').read_text())['remote_head']==head
    assert runner.git(repo,'rev-parse','HEAD')==marker['base']
    assert runner.git(remote,'rev-parse','main')==head
