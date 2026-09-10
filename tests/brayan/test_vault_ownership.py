"""Ownership guard and native runner integration tests."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "brayan-personalization" / "runtime" / "scripts"
COMMON = SCRIPTS / "vault_ownership_common.py"
RUNNER = SCRIPTS / "vault_ownership.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def contract(home: Path, *, role: str = "owner", hostname: str | None = None, repo: Path | None = None) -> dict:
    state = home / "ownership-state"
    return {
        "version": 1,
        "hostname": hostname or socket.gethostname(),
        "role": role,
        "owner_hostname": socket.gethostname(),
        "hermes_home": str(home),
        "vault_path": str(home / "vault"),
        "repo_path": str(repo or home / "repo"),
        "state_dir": str(state),
        "snapshot_root": str(state / "snapshots"),
        "contribution_root": str(state / "contributions"),
        "repository": "local/test-vault",
        "remote": "origin",
        "branch": "main",
        "maintenance_branch": "main",
        "hermes_source": str(ROOT),
        "delivery_targets": {"job-1": "local"},
    }


def write_contract(home: Path, value: dict) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "vault-ownership.json").write_text(json.dumps(value), encoding="utf-8")


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=check)


def init_repo(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "-b", "main")
    git(seed, "config", "user.name", "Test")
    git(seed, "config", "user.email", "test@example.invalid")
    (seed / "README.md").write_text("base\n", encoding="utf-8")
    git(seed, "add", "README.md")
    git(seed, "commit", "-m", "base")
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "origin", "main")
    repo = tmp_path / "repo"
    git(tmp_path, "clone", "-b", "main", str(remote), str(repo))
    git(repo, "config", "user.name", "Canonical")
    git(repo, "config", "user.email", "canonical@example.invalid")
    return repo, remote


def test_contract_preserves_public_symlink_identity(tmp_path):
    common = load_module(COMMON, "vault_ownership_common_symlink")
    home = tmp_path / "hermes"
    value = contract(home)
    write_contract(home, value)
    target = tmp_path / "snapshot"
    target.mkdir()
    Path(value["vault_path"]).symlink_to(target, target_is_directory=True)
    assert common.load_contract(home)["vault_path"] == value["vault_path"]


def test_contract_identity_is_checked_before_lock_directory_creation(tmp_path, monkeypatch):
    common = load_module(COMMON, "vault_ownership_common_identity")
    home = tmp_path / "hermes"
    value = contract(home, hostname="not-this-host")
    write_contract(home, value)

    with pytest.raises(common.OwnershipError, match="hostname"):
        common.load_contract(home)

    assert not Path(value["state_dir"]).exists()


def test_owner_lock_refuses_a_second_process_while_first_operation_is_live(tmp_path):
    common = load_module(COMMON, "vault_ownership_common_lock")
    home = tmp_path / "hermes"
    value = contract(home)
    write_contract(home, value)
    loaded = common.load_contract(home)

    child = (
        "import sys; "
        "from vault_ownership_common import owner_lock; "
        f"c=owner_lock({loaded!r}); "
        "\ntry:\n with c: print('acquired')\n"
        "except Exception as e: print(type(e).__name__ + ':' + str(e)); raise SystemExit(3)"
    )
    env = {**os.environ, "PYTHONPATH": str(SCRIPTS)}
    with common.owner_lock(loaded):
        result = subprocess.run([sys.executable, "-c", child], env=env, text=True, capture_output=True)
    assert result.returncode == 3
    assert "lock" in result.stdout.lower()


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


def test_runner_preserves_failed_work_and_blocks_next_acquire(tmp_path):
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
    preserved = list((state / "worktrees" / job_id).iterdir())
    assert preserved and (preserved[0] / "failed.txt").exists()
    second = subprocess.run([sys.executable, str(RUNNER), job_id], cwd=job_dir, env=env, text=True, capture_output=True)
    assert second.returncode != 0
    assert "preserved" in (second.stderr + second.stdout).lower()


def test_runner_audits_spawned_background_gate_before_worktree_creation(tmp_path):
    runner = load_module(RUNNER, "vault_ownership_runner_audit")
    script = tmp_path / "unsafe.py"
    script.write_text(
        "import subprocess\nsubprocess.Popen(['sleep', '10'], start_new_session=True)\n", encoding="utf-8"
    )
    findings = runner.audit_script_for_background_escape(script)
    assert findings
    assert any("Popen" in finding for finding in findings)
