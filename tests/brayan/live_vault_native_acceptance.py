"""Mandatory real user-systemd live-host acceptance; ordinary CI has no bus.
Original assertions moved unchanged. Run evidence/original_native_live.py.
"""
import json,os,subprocess,sys
from pathlib import Path
import psutil,pytest
from test_vault_ownership import ROOT,SCRIPTS,RUNNER,contract,write_contract,init_repo,git,load_module
from test_project_scan_outcomes import setup_scan
sys.path.insert(0,str(SCRIPTS))
import vault_ownership as runner

def test_runner_holds_owner_lock_through_gate_child_commit_and_push(tmp_path):
    repo, remote = init_repo(tmp_path)
    home = tmp_path / "hermes"
    vault = repo
    value = contract(home, repo=repo)
    value["remote"] = str(remote)
    write_contract(home, value)
    state = Path(value["state_dir"])
    job_id = "job-1"
    job_dir = state / "jobs" / job_id
    job_dir.mkdir(parents=True)
    (state / "jobs-original.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": job_id,
                        "name": "test writer",
                        "script": "gate.py",
                        "prompt": "write the test change",
                        "deliver": "local",
                        "enabled": True,
                        "no_agent": True,
                        "allowed_paths": ["result.txt", "lock-check.txt"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    scripts = home / "scripts"
    scripts.mkdir()
    (scripts / "gate.py").write_text(
        "import fcntl, os, pathlib\n"
        "root=pathlib.Path(os.environ['HERMES_VAULT_ROOT'])\n"
        "lock=pathlib.Path(os.environ['HERMES_HOME'])/'ownership-state'/'owner.lock'\n"
        "with lock.open('r+') as f:\n"
        " try: fcntl.flock(f.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB); state='unlocked'\n"
        " except BlockingIOError: state='locked'\n"
        "(root/'lock-check.txt').write_text(state)\n"
        "(root/'result.txt').write_text('child')\n"
        "print('child response')\n", encoding="utf-8"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_hermes = bin_dir / "hermes"
    fake_hermes.write_text(
        "#!/bin/sh\n"
        "python3 - <<'PY'\n"
        "import fcntl, os, pathlib, sys\n"
        "lock = pathlib.Path(os.environ['HERMES_HOME']) / 'ownership-state' / 'owner.lock'\n"
        "with lock.open('r+') as fh:\n"
        "    try:\n"
        "        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
        "        pathlib.Path(os.environ['HERMES_VAULT_ROOT'], 'lock-check.txt').write_text('unlocked')\n"
        "    except BlockingIOError:\n"
        "        pathlib.Path(os.environ['HERMES_VAULT_ROOT'], 'lock-check.txt').write_text('locked')\n"
        "pathlib.Path(os.environ['HERMES_VAULT_ROOT'], 'result.txt').write_text('child')\n"
        "print('child response')\n"
        "PY\n",
        encoding="utf-8",
    )
    fake_hermes.chmod(0o755)

    env = {**os.environ, "HERMES_HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    result = subprocess.run(
        [sys.executable, str(RUNNER), job_id],
        cwd=job_dir,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "child response"
    assert (repo / "result.txt").read_text(encoding="utf-8") == "child"
    assert (repo / "lock-check.txt").read_text(encoding="utf-8") == "locked"
    git(repo, "fetch", "origin", "main")
    assert git(repo, "rev-parse", "HEAD").stdout == git(repo, "rev-parse", "origin/main").stdout
    message = git(repo, "log", "-1", "--format=%B").stdout
    assert "Vault-Ownership-Job: job-1" in message
    assert not (state / "worktrees" / job_id).exists()


def test_contained_failure_is_archived_and_next_job_publishes(tmp_path):
    repo, remote = init_repo(tmp_path)
    home = tmp_path / "hermes"
    value = contract(home, repo=repo)
    value["remote"] = str(remote)
    write_contract(home, value)
    state = Path(value["state_dir"])
    job_id = "job-1"
    job_dir = state / "jobs" / job_id
    job_dir.mkdir(parents=True)
    (state / "jobs-original.json").write_text(
        json.dumps({"jobs": [{"id": job_id, "prompt": "fail", "enabled": True, "script": "failure.py", "no_agent": True, "allowed_paths": ["failed.txt"]}]}), encoding="utf-8"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_hermes = bin_dir / "hermes"
    fake_hermes.write_text(
        "#!/bin/sh\nprintf failed > \"$HERMES_VAULT_ROOT/failed.txt\"\nexit 7\n", encoding="utf-8"
    )
    fake_hermes.chmod(0o755)
    env = {**os.environ, "HERMES_HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    scripts = home / 'scripts'
    scripts.mkdir()
    (scripts / 'failure.py').write_text("import os, pathlib; pathlib.Path(os.environ['HERMES_VAULT_ROOT'], 'failed.txt').write_text('failed'); raise SystemExit(7)")
    first = subprocess.run([sys.executable, str(RUNNER), job_id], cwd=job_dir, env=env, text=True, capture_output=True)
    assert first.returncode != 0
    assert not (state / "pending-owner.json").exists(), first.stdout + first.stderr
    archives = list((state / "failed").iterdir())
    assert len(archives) == 1
    manifest = json.loads((archives[0] / "manifest.json").read_text(encoding="utf-8"))
    archived_marker = json.loads((archives[0] / "pending-owner.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert type(archived_marker["pid"]) is int and archived_marker["pid"] > 0
    assert isinstance(archived_marker["pid_created"], float)
    assert (archives[0] / "files" / "failed.txt").read_text(encoding="utf-8") == "failed"
    preserved = list((state / "worktrees" / job_id).iterdir())
    assert preserved and (preserved[0] / "failed.txt").exists()

    (scripts / "failure.py").write_text(
        "import os, pathlib; pathlib.Path(os.environ['HERMES_VAULT_ROOT'], 'failed.txt').write_text('recovered')",
        encoding="utf-8",
    )
    second = subprocess.run([sys.executable, str(RUNNER), job_id], cwd=job_dir, env=env, text=True, capture_output=True)
    assert second.returncode == 0, second.stdout + second.stderr
    assert (repo / "failed.txt").read_text(encoding="utf-8") == "recovered"
    assert git(repo, "ls-remote", str(remote), "refs/heads/main").stdout.split()[0] == git(repo, "rev-parse", "HEAD").stdout.strip()


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
        state = Path(cfg['state_dir'])
        assert not (state / 'pending-owner.json').exists()
        archives = list((state / 'failed').iterdir())
        assert len(archives) == 1, 'Contained escape must be archived, never published'
        receipt = json.loads((archives[0] / 'records' / 'run' / 'result.json').read_text())
        assert receipt['success'] is False
        assert receipt['error'] == 'Native job left background descendants; scope teardown required'
        assert receipt['descendant_cleanup']['deferred_to_scope'] is True
        marker = json.loads((archives[0] / 'pending-owner.json').read_text())
        frozen = marker['containment_proof']['unknown']
        assert any(record['pid'] == int(pidfile.read_text()) for record in frozen), frozen
        assert not psutil.pid_exists(int(pidfile.read_text())) or psutil.Process(int(pidfile.read_text())).status() == psutil.STATUS_ZOMBIE
        assert runner.git(remote, 'rev-parse', 'main') == runner.git(repo, 'rev-parse', 'HEAD')
    finally:
        if pidfile.exists():
            try:
                psutil.Process(int(pidfile.read_text())).kill()
            except psutil.NoSuchProcess:
                pass


def test_native_script_publishes_good_review_but_reports_partial_failure(tmp_path, monkeypatch, capsys):
    import shutil
    from test_vault_ownership import init_repo, git, RUNNER
    scanner, vault = setup_scan(tmp_path, monkeypatch)
    git_dir = tmp_path / 'git'
    git_dir.mkdir()
    repo, remote = init_repo(git_dir)
    shutil.copytree(vault / 'projects', repo / 'projects')
    git(repo, 'add', 'projects')
    git(repo, 'commit', '-m', 'project fixtures')
    git(repo, 'push', 'origin', 'main')
    cfg = contract(scanner.HERMES_HOME, repo=repo)
    cfg['remote'] = str(remote)
    write_contract(scanner.HERMES_HOME, cfg)
    scripts = scanner.HERMES_HOME / 'scripts'
    scripts.mkdir()
    for name in ('project_review_scan.py', 'project_review_history_retention.py', 'vault_ownership_common.py'):
        shutil.copyfile(SCRIPTS / name, scripts / name)
    shutil.copyfile(tmp_path / 'fake-hermes', tmp_path / 'hermes')
    with (tmp_path / 'hermes').open('a') as stream:
        stream.write('print(\'{"ready_count": 0}\')\n')
    (tmp_path / 'hermes').chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + ':' + __import__('os').environ['PATH'])
    runner = load_module(RUNNER, 'project_native_outcome_runner')
    with pytest.raises(runner.AgentDeclaredFailure):
        runner.execute_job(cfg, {'id':'project-test', 'script':'project_review_scan.py', 'no_agent':True,
            'allowed_paths':['projects/'], 'ownership_timeout':30})
    assert capsys.readouterr().out.splitlines()[0] == '[CRON_FAILURE]'
    assert 'Reviewed, still paused.' in (repo / 'projects/good/README.md').read_text()
    assert not (Path(cfg['state_dir']) / 'pending-owner.json').exists()
    assert git(repo, 'rev-parse', 'HEAD').stdout.strip() == git(repo, 'ls-remote', str(remote), 'refs/heads/main').stdout.split()[0]

