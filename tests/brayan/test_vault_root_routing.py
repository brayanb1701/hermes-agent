"""Effective-root propagation and foreground opportunity dispatch contracts."""
import os
from pathlib import Path
import sys
import pytest
from test_vault_ownership import SCRIPTS,load_module,contract,write_contract


@pytest.mark.parametrize('name,field',[
    ('opportunity_preparation_ready_scan','VAULT'),('opportunity_closeout_scan','VAULT'),
    ('vault_structure_audit','VAULT'),('project_review_scan','VAULT'),
    ('project_state_audit','VAULT'),('vault_generated_retention','DEFAULT_VAULT'),
    ('project_review_history_retention','DEFAULT_VAULT'),('inbox_triage_wake_gate','DEFAULT_VAULT'),
    ('project_scaffold','VAULT'),('opportunity_scaffold','DEFAULT_VAULT'),
    ('topic_recommendation_retention','DEFAULT_PATH')])
def test_effective_root_reaches_original_helpers(tmp_path,monkeypatch,name,field):
    root=tmp_path/'isolated'
    root.mkdir()
    monkeypatch.setenv('HERMES_VAULT_ROOT',str(root))
    sys.path.insert(0,str(SCRIPTS))
    mod=load_module(SCRIPTS/(name+'.py'),name+'_root_test')
    assert Path(getattr(mod,field)).is_relative_to(root)


@pytest.mark.parametrize('name,entry', [('opportunity_preparation_ready_scan','launch_opportunity'),('opportunity_closeout_scan','launch_closeout'),('project_review_scan','launch_project')])
def test_opportunity_dispatch_waits_for_child_before_return(tmp_path,monkeypatch,name,entry):
    root=tmp_path/'isolated'
    root.mkdir()
    monkeypatch.setenv('HERMES_VAULT_ROOT',str(root))
    home=tmp_path/'hermes'
    cfg=contract(home)
    write_contract(home,cfg)
    monkeypatch.setenv('HERMES_HOME',str(home))
    sys.path.insert(0,str(SCRIPTS))
    mod=load_module(SCRIPTS/(name+'.py'),name+'_child_test')
    monkeypatch.setattr(mod,'STATE_DIR',tmp_path/'state')
    monkeypatch.setattr(mod,'LOG_DIR',tmp_path/'logs')
    monkeypatch.setattr(mod,'build_prompt',lambda item:'Test child')
    executable=tmp_path/'hermes-child'
    executable.write_text('#!/bin/sh\nsleep 0.2\nprintf completed > "$HERMES_VAULT_ROOT/child.done"\n')
    executable.chmod(0o755)
    monkeypatch.setattr(mod.shutil,'which',lambda _:str(executable))
    item={k:'test' for k in ['slug','stem','opportunity_path','title','opportunity_kind','workflow_mode','priority','closeout_input_path','proposed_status','proposed_result_status']}
    getattr(mod,entry)(item)
    assert (root/'child.done').read_text()=='completed'
