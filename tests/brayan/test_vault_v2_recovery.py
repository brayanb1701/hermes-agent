"""V2 crash recovery uses unit intent, not fabricated completion receipts."""
import json
from pathlib import Path
import pytest
from test_vault_owner_recovery import failed_state, runner


def test_v2_intent_only_archives_missing_receipt_never_publishes(tmp_path,runner,monkeypatch):
    cfg,repo,remote,state,root,run_dir,run_id,marker=failed_state(tmp_path,runner)
    from vault_run_scope import scope_intent
    marker.update(version=2, containment=scope_intent(run_id,run_dir))
    (run_dir/'result.json').unlink()
    (state/'pending-owner.json').write_text(json.dumps(marker))
    monkeypatch.setattr(runner,'_close_run_scope',lambda *args: {'contained':True,'status':'launch-unconfirmed','observed':[],'unknown':[]})
    monkeypatch.setattr(runner,'_root_aware_processes',lambda *args,**kw: pytest.fail('V2 must not scan same-user processes'))
    result=runner.abandon_incomplete(cfg,run_id)
    assert result['status']=='archived'
    archive=Path(result['archive'])
    assert (archive/'files/changed.txt').read_bytes()==b'failed evidence\n'
    assert not (run_dir/'result.json').exists()
    incomplete=json.loads((archive/'incomplete-failure.json').read_text())
    assert incomplete['receipt']=='missing' and incomplete['status']=='incomplete-failure'
    assert incomplete['containment']['status']=='launch-unconfirmed'
