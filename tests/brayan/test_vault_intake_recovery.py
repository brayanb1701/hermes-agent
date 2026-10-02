"""Recognized intake marker recovery: no sweeping dirty canonical edits."""
import json
from pathlib import Path
import pytest
from test_vault_native_intake import setup
from test_vault_ownership import RUNNER,load_module,git


def test_clean_orphan_reconciles_through_shared_reader(tmp_path,monkeypatch):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    intent=plugin._begin(cfg,event,'session')
    runner=load_module(RUNNER,'intake_recover_runner')
    result=runner.reconcile_pending(cfg,intent['id'])
    assert result['status']=='intake-cleared'
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()


def test_dirty_orphan_stays_operator_required(tmp_path,monkeypatch):
    plugin,cfg,repo,remote,event,gateway=setup(tmp_path,monkeypatch)
    intent=plugin._begin(cfg,event,'session')
    (repo/'preserved.md').write_bytes(b'raw\x00capture')
    runner=load_module(RUNNER,'intake_dirty_runner')
    with pytest.raises(runner.OwnershipError,match='dirty'):
        runner.reconcile_pending(cfg,intent['id'])
    assert (repo/'preserved.md').read_bytes()==b'raw\x00capture'
    assert (Path(cfg['state_dir'])/'pending-owner.json').exists()
