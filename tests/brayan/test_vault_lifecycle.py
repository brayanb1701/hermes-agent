"""Native subprocess lifecycle regression: orphaned setsid workers cannot escape."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import psutil

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'brayan-personalization/runtime/scripts'
sys.path.insert(0, str(SCRIPTS))
import vault_ownership as runner
from test_vault_ownership import contract, write_contract, init_repo


def test_publication_refuses_changed_remote_even_when_fast_forward_possible(tmp_path):
    repo,remote=init_repo(tmp_path)
    old=runner.git(repo,'rev-parse','HEAD')
    (repo/'second.md').write_text('second')
    runner.git(repo,'add','second.md')
    runner.git(repo,'commit','-m','second')
    base=runner.git(repo,'rev-parse','HEAD')
    runner.git(repo,'push',str(remote),'HEAD:main')
    (repo/'third.md').write_text('third')
    runner.git(repo,'add','third.md')
    runner.git(repo,'commit','-m','third')
    runner.git(remote,'update-ref','refs/heads/main',old,base)
    cfg=contract(tmp_path/'h',repo=repo)
    cfg['remote']=str(remote)
    import pytest
    with pytest.raises(runner.OwnershipError):
        runner.publish(repo,cfg,base)
    assert runner.git(remote,'rev-parse','main')==old


def test_native_worker_reaps_detached_descendant_before_publication(tmp_path, monkeypatch):
    repo, remote = init_repo(tmp_path)
    home = tmp_path / 'hermes'
    cfg = contract(home, repo=repo)
    cfg['remote'] = str(remote)
    write_contract(home, cfg)
    monkeypatch.setenv('HERMES_HOME', str(home))
    scripts = home / 'scripts'
    scripts.mkdir()
    pidfile = tmp_path / 'descendant.pid'
    # The gate exits leaving a detached worker with closed pipes, the historical
    # opportunity-launcher pattern. Test never allows it to touch a real vault.
    (scripts / 'escape.py').write_text(
        "import subprocess, sys, pathlib\n"
        f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid))\n"
        "print('done')\n")
    try:
        try:
            runner.execute_job(cfg, dict(id='escape', no_agent=True, script='escape.py', allowed_paths=['out/']))
        except runner.OwnershipError:
            pass
        pid = int(pidfile.read_text())
        assert not psutil.pid_exists(pid), 'Detached writer escaped completion boundary'
        assert (Path(cfg['state_dir']) / 'pending-owner.json').exists(), 'Escape must block publication'
    finally:
        if pidfile.exists():
            try:
                psutil.Process(int(pidfile.read_text())).kill()
            except psutil.NoSuchProcess:
                pass


def test_agent_commit_in_worktree_cannot_bypass_diff_validation(tmp_path):
    import pytest
    repo, remote = init_repo(tmp_path)
    cfg = contract(tmp_path/'home', repo=repo)
    cfg['remote'] = str(remote)
    base=runner.git(repo,'rev-parse','HEAD')
    def executor(job, root, run):
        (root/'forbidden.md').write_text('unreviewed')
        runner.git(root,'add','--all')
        runner.git(root,'commit','-m','agent moved head')
        return 'done'
    with pytest.raises(runner.OwnershipError, match='HEAD'):
        runner.execute_job(cfg,dict(id='movehead',allowed_paths=['inbox/']),executor=executor)
    assert runner.git(remote,'rev-parse','main')==base
    assert (Path(cfg['state_dir'])/'pending-owner.json').exists()


def test_missing_output_scope_refused_before_executor(tmp_path):
    import pytest
    repo,remote=init_repo(tmp_path)
    cfg=contract(tmp_path/'home',repo=repo)
    cfg['remote']=str(remote)
    called=[]
    with pytest.raises(runner.OwnershipError,match='allowed_paths'):
        runner.execute_job(cfg,dict(id='unscoped'),executor=lambda *args:called.append(True))
    assert not called
    assert not Path(cfg['state_dir']).exists()


def test_success_after_recovery_keeps_old_work_but_clears_new_marker(tmp_path):
    repo, remote = init_repo(tmp_path)
    cfg = contract(tmp_path/'home',repo=repo)
    cfg['remote']=str(remote)
    older=Path(cfg['state_dir'])/'worktrees'/'retry'/'preserved-failure'
    older.mkdir(parents=True)
    (older/'evidence.txt').write_text('must retain')
    def executor(job, root, run):
        (root/'result.md').write_text('published')
        return 'done'
    result=runner.execute_job(cfg,dict(id='retry',allowed_paths=['result.md']),executor=executor)
    assert result=='done'
    assert (older/'evidence.txt').read_text()=='must retain'
    assert not (Path(cfg['state_dir'])/'pending-owner.json').exists()
    assert (repo/'result.md').read_text()=='published'


def test_markdown_hard_line_breaks_are_valid_outputs(tmp_path):
    repo, remote=init_repo(tmp_path)
    (repo/'note.md').write_text('Original text  \nSecond line\n\n')
    assert runner.validate_diff(repo,['note.md'])==['note.md']


def test_readonly_canonical_refused_before_publication_or_state(tmp_path):
    import pytest
    repo,remote=init_repo(tmp_path)
    cfg=contract(tmp_path/'home',repo=repo)
    cfg['remote']=str(remote)
    base=runner.git(repo,'rev-parse','HEAD')
    mode=repo.stat().st_mode
    repo.chmod(0o555)
    try:
        with pytest.raises(runner.OwnershipError,match='writable'):
            runner.execute_job(cfg,dict(id='permissions',allowed_paths=['note.md']),executor=lambda *args:'unused')
        assert runner.git(remote,'rev-parse','main')==base
        assert not Path(cfg['state_dir']).exists()
    finally:
        repo.chmod(mode)
