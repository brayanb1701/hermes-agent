"""Real Git recovery of interrupted owner publication, without rerunning agents."""
import json
from pathlib import Path

import pytest

from test_vault_owner_recovery import failed_state
from test_vault_ownership import RUNNER, git, load_module


@pytest.fixture
def runner():
    return load_module(RUNNER, 'vault_publication_resume_tests')


def publication(tmp_path, runner, phase='publishing'):
    cfg, repo, remote, state, root, run_dir, run, marker = failed_state(tmp_path, runner)
    cfg['managed_jobs'] = {marker['job']: {'allowed_paths': marker['intent']['allowed_paths']}}
    (run_dir / 'job.json').write_text(json.dumps({'id': marker['job']}))
    receipt = json.loads((run_dir / 'result.json').read_text())
    receipt.update(success=True, error=None)
    (run_dir / 'result.json').write_text(json.dumps(receipt))
    git(root, 'add', '--all')
    message = (f"Managed vault job {marker['job']}\n\nVault-Ownership-Job: {marker['job']}\n"
               f"Source-Host: {cfg['hostname']}\nSession: {run}\nBase-SHA: {marker['base']}")
    git(root, 'commit', '-m', message)
    head = git(root, 'rev-parse', 'HEAD').stdout.strip()
    marker.update(phase=phase, head=head)
    if phase == 'integrating':
        marker['remote_head'] = head
    (state / 'pending-owner.json').write_text(json.dumps(marker))
    return cfg, repo, remote, state, root, run_dir, run, marker


def test_scope_rejects_rename_from_unapproved_source(tmp_path, runner):
    cfg, repo, remote, state, root, run_dir, run, marker = failed_state(tmp_path, runner)
    (root / 'changed.txt').unlink()
    git(root, 'mv', 'README.md', 'changed.txt')
    with pytest.raises(runner.OwnershipError, match='Out-of-scope'):
        runner.validate_diff(root, ['changed.txt'])


def test_network_git_timeout_is_bounded(tmp_path, runner, monkeypatch):
    import subprocess
    import sys
    import time
    import psutil
    command = tmp_path / 'git'
    command.write_text(f'#!{sys.executable}\nimport subprocess,time\np=subprocess.Popen(["sleep","60"])\nopen({str(tmp_path / "child")!r},"w").write(str(p.pid))\ntime.sleep(60)\n')
    command.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + ':' + __import__('os').environ['PATH'])
    monkeypatch.setenv('GIT_SSH_COMMAND', 'ssh')
    before = time.monotonic()
    with pytest.raises(runner.OwnershipError, match='timed out'):
        runner.git(tmp_path, 'ls-remote', 'origin', network_timeout=0.2)
    assert time.monotonic() - before < 3
    try:
        child = psutil.Process(int((tmp_path / 'child').read_text()))
        assert child.status() == psutil.STATUS_ZOMBIE or not child.is_running()
    except psutil.NoSuchProcess:
        pass


def test_sync_tick_recovers_pending_publication(tmp_path, runner, monkeypatch):
    import sys
    import vault_contributions as contributions
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    monkeypatch.setitem(sys.modules, 'vault_ownership', runner)
    monkeypatch.setattr(contributions, 'list_pending_reviews', lambda *a, **k: [])
    assert contributions.process_pending_reviews(cfg)['processed'] == []
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == marker['head']
    assert not (state / 'pending-owner.json').exists()


def test_configured_lock_wait_survives_contention(tmp_path, runner):
    import subprocess
    import sys
    import time
    from vault_ownership_common import owner_lock
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    child = subprocess.Popen([sys.executable, '-c',
        'import fcntl,sys,time; f=open(sys.argv[1],"a+"); fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); time.sleep(2.3)',
        str(state / 'owner.lock')], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'locked'
        with owner_lock(cfg, wait_seconds=4):
            assert child.wait(timeout=2) == 0
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()


@pytest.mark.parametrize('boot, rooted, expected', [(1000, False, None), (50, False, 'fully inspect'), (1000, True, 'Processes still reference'), (None, False, 'fully inspect')])
def test_publication_scan_after_reboot(tmp_path, runner, monkeypatch, boot, rooted, expected):
    import os
    import psutil
    class Candidate:
        pid = 987654
        def uids(self): return type('Uids', (), {'real': os.getuid()})()
        def create_time(self): return 2000.0
        def status(self): return psutil.STATUS_SLEEPING
        def cwd(self): raise psutil.AccessDenied(self.pid)
        def cmdline(self): return ['worker', str(tmp_path / 'root')] if rooted else ['daemon']
    def boot_time():
        if boot is None: raise OSError('unavailable')
        return boot
    monkeypatch.setattr(psutil, 'process_iter', lambda _attrs: [Candidate()])
    monkeypatch.setattr(psutil, 'boot_time', boot_time)
    if expected:
        with pytest.raises(runner.OwnershipError, match=expected):
            runner._root_aware_processes(tmp_path / 'root', None, not_before=100, publication=True)
    else:
        runner._root_aware_processes(tmp_path / 'root', None, not_before=100, publication=True)


def test_explicit_abandon_preserves_incomplete_work_without_receipt(tmp_path, runner):
    cfg, repo, remote, state, root, run_dir, run, marker = failed_state(tmp_path, runner)
    (run_dir / 'result.json').unlink()
    with pytest.raises(runner.OwnershipError):
        runner.reconcile_pending(cfg, run)
    result = runner.abandon_incomplete(cfg, run)
    assert result['status'] == 'abandoned'
    assert root.is_dir()
    assert not (run_dir / 'result.json').exists()
    assert not (state / 'pending-owner.json').exists()
    archive = state / 'failed' / run
    manifest = json.loads((archive / 'manifest.json').read_text())
    assert manifest['kind'] == 'abandoned-owner-job'
    assert 'abandonment.json' in manifest['artifacts']
    record = json.loads((archive / 'abandonment.json').read_text())
    assert record['receipt'] == 'missing'
    assert (archive / 'files' / 'changed.txt').read_text() == 'failed evidence\n'
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == marker['base']
    assert git(repo, 'ls-remote', str(remote), 'refs/heads/main').stdout.split()[0] == marker['base']


def test_abandon_refuses_existing_receipt(tmp_path, runner):
    cfg, repo, remote, state, root, run_dir, run, marker = failed_state(tmp_path, runner)
    with pytest.raises(runner.OwnershipError, match='receipt'):
        runner.abandon_incomplete(cfg, run)
    assert (state / 'pending-owner.json').exists()


def test_abandon_scan_detects_environment_only_orphan(tmp_path, runner):
    import os, subprocess, sys, psutil
    root = tmp_path / 'root'
    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                            cwd=tmp_path, env=dict(os.environ, HERMES_VAULT_ROOT=str(root)))
    try:
        with pytest.raises(runner.OwnershipError, match='Processes still reference'):
            runner._root_aware_processes(root, None, not_before=psutil.Process(proc.pid).create_time() - 1,
                                         inspect_environment=True)
    finally:
        proc.kill()
        proc.wait()


def test_sync_tick_is_silent_when_writer_holds_lock(tmp_path, runner, monkeypatch):
    import contextlib
    import vault_contributions as contributions
    from vault_ownership_common import OwnershipBusy
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    @contextlib.contextmanager
    def busy(_contract):
        raise OwnershipBusy('busy')
        yield
    monkeypatch.setattr(contributions, 'owner_lock', busy)
    assert contributions.process_pending_reviews(cfg) == {'processed': [], 'wakeAgent': False, 'status': 'writer-busy'}
    assert (state / 'pending-owner.json').exists()


def test_publish_failure_preserves_report_in_failure_output(tmp_path, runner, monkeypatch, capsys):
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    runner.reconcile_pending(cfg, run)
    def execute(job, root, run_dir):
        (root / 'changed.txt').write_text('new valid work')
        return 'REPORT STILL AVAILABLE'
    def publish(*args):
        raise runner.OwnershipError('simulated remote failure')
    monkeypatch.setattr(runner, 'publish', publish)
    with pytest.raises(runner.OwnershipError):
        runner.execute_job(cfg, {'id': marker['job'], 'allowed_paths': ['changed.txt']}, executor=execute)
    assert 'REPORT STILL AVAILABLE' in capsys.readouterr().out
    assert json.loads((state / 'pending-owner.json').read_text())['phase'] == 'publishing'


@pytest.mark.parametrize('text', [None, '', '[CRON_FAILURE]', '[CRON_FAILURE]\nfailed', '[CRON_FAILURE]  \nfailed', '\n[CRON_FAILURE]\nfailed', 'quoted [CRON_FAILURE]', '[CRON_FAILURE] not standalone'])
def test_declared_failure_matches_scheduler(tmp_path, runner, text):
    from cron.scheduler import _cron_failure_marker_error
    assert runner._declared_failure(text) == _cron_failure_marker_error(text)


@pytest.mark.parametrize('changed', [False, True])
def test_declared_failure_reports_failure_after_valid_publication(tmp_path, runner, capsys, changed):
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    runner.reconcile_pending(cfg, run)
    def execute(job, root, run_dir):
        if changed:
            (root / 'changed.txt').write_text('valid partial work')
        return '[CRON_FAILURE]\nSome reviews failed\nUseful report'
    with pytest.raises(runner.AgentDeclaredFailure, match='Agent declared failure after'):
        runner.execute_job(cfg, {'id': marker['job'], 'allowed_paths': ['changed.txt']}, executor=execute)
    assert '[CRON_FAILURE]' in capsys.readouterr().out
    assert not (state / 'pending-owner.json').exists()
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == git(repo, 'ls-remote', str(remote), 'refs/heads/main').stdout.split()[0]
    if changed:
        assert (repo / 'changed.txt').read_text() == 'valid partial work'


@pytest.mark.parametrize('value', ['300', True, -1, 1201])
def test_contract_rejects_invalid_lock_wait(tmp_path, runner, value):
    from vault_ownership_common import load_contract
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    cfg['owner_lock_wait_seconds'] = value
    Path(cfg['hermes_home'], 'vault-ownership.json').write_text(json.dumps(cfg))
    with pytest.raises(runner.OwnershipError, match='lock wait'):
        load_contract(cfg['hermes_home'])


def test_failed_push_resumes_publication(tmp_path, runner):
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    result = runner.reconcile_pending(cfg, run)
    assert result['status'] == 'recovered'
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == marker['head']
    assert git(repo, 'ls-remote', str(remote), 'refs/heads/main').stdout.split()[0] == marker['head']
    assert git(repo, 'rev-parse', f'refs/vault-ownership/runs/{run}').stdout.strip() == marker['head']
    assert not (state / 'pending-owner.json').exists()
    assert (state / 'recovered' / run / 'pending-owner.json').exists()
    assert (state / 'recovered' / run / 'commit.bundle').is_file()
    assert runner.reconcile_pending(cfg)['status'] == 'no-pending-owner'


@pytest.mark.parametrize('phase', ['publishing', 'integrating'])
def test_push_already_landed_resumes_integration(tmp_path, runner, phase):
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner, phase)
    git(root, 'push', str(remote), 'HEAD:main')
    hook = remote / 'hooks' / 'pre-receive'
    hook.write_text('#!/bin/sh\nexit 1\n')
    hook.chmod(0o755)
    runner.reconcile_pending(cfg, run)
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == marker['head']
    assert not (state / 'pending-owner.json').exists()


def test_foreign_remote_is_never_overwritten(tmp_path, runner):
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    (repo / 'foreign.txt').write_text('foreign')
    git(repo, 'add', '--all')
    git(repo, 'commit', '-m', 'foreign writer')
    foreign = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    git(repo, 'push', str(remote), 'HEAD:main')
    with pytest.raises(runner.OwnershipError):
        runner.reconcile_pending(cfg, run)
    assert (state / 'pending-owner.json').exists()
    assert git(repo, 'ls-remote', str(remote), 'refs/heads/main').stdout.split()[0] == foreign


@pytest.mark.parametrize('mutation', ['failed-receipt', 'dirty-root', 'wrong-branch', 'narrowed-scope', 'wrong-message', 'extra-commit', 'symlink', 'rename'])
def test_unproven_publication_never_pushes(tmp_path, runner, mutation):
    cfg, repo, remote, state, root, run_dir, run, marker = publication(tmp_path, runner)
    if mutation == 'failed-receipt':
        receipt = json.loads((run_dir / 'result.json').read_text())
        receipt['success'] = False
        (run_dir / 'result.json').write_text(json.dumps(receipt))
    elif mutation == 'dirty-root':
        (root / 'stray').write_text('stray')
    elif mutation == 'wrong-branch':
        git(repo, 'switch', '-c', 'wrong')
    elif mutation == 'narrowed-scope':
        cfg['managed_jobs'][marker['job']]['allowed_paths'] = ['other/']
    else:
        message = git(root, 'log', '-1', '--format=%B').stdout.strip()
        if mutation == 'wrong-message':
            message = 'unrelated author'
        elif mutation == 'extra-commit':
            (root / 'changed.txt').write_text('second')
        elif mutation == 'symlink':
            (root / 'changed.txt').unlink()
            (root / 'changed.txt').symlink_to('/etc/passwd')
        elif mutation == 'rename':
            (root / 'changed.txt').unlink()
            git(root, 'mv', 'README.md', 'changed.txt')
        git(root, 'add', '--all')
        args = ['commit', '-m', message]
        if mutation != 'extra-commit':
            args.insert(1, '--amend')
        git(root, *args)
        marker['head'] = git(root, 'rev-parse', 'HEAD').stdout.strip()
        (state / 'pending-owner.json').write_text(json.dumps(marker))
    with pytest.raises(runner.OwnershipError):
        runner.reconcile_pending(cfg, run)
    assert (state / 'pending-owner.json').exists()
    assert git(repo, 'ls-remote', str(remote), 'refs/heads/main').stdout.split()[0] == marker['base']
