"""Run-local daemon cleanup never adopts or signals an unrelated PID."""
from pathlib import Path
import sys
import pytest
from test_vault_ownership import RUNNER,load_module
load_module(RUNNER,'browser_runner_imports')


def test_empty_runtime_needs_no_dependency(tmp_path,monkeypatch):
    monkeypatch.setenv('BH_RUNTIME_DIR',str(tmp_path))
    module=load_module(RUNNER.parent/'vault_run_browser.py','browser_disposal_tests')
    result=module.shutdown_browsers({'expected_cgroup':'/test'})
    assert result['ok'] and result['daemons']==[] and result['extra_tabs']=='unverified'


def test_names_capped_and_no_external_paths(tmp_path,monkeypatch):
    monkeypatch.setenv('BH_RUNTIME_DIR',str(tmp_path))
    for n in range(33): (tmp_path/f'bu-n{n}.pid').write_text('1')
    module=load_module(RUNNER.parent/'vault_run_browser.py','browser_cap_tests')
    result=module.shutdown_browsers({'expected_cgroup':'/test'})
    assert not result['ok'] and result['error']=='endpoint-bound'
