"""Fail-closed owner-job reconciliation and publication-boundary tests."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

import pytest
import psutil

from test_vault_ownership import RUNNER, contract, git, init_repo, load_module, write_contract


@pytest.fixture
def runner():
    return load_module(RUNNER, "vault_owner_recovery_tests")


def failed_state(tmp_path, runner, *, phase="executing", legacy=False):
    repo, remote = init_repo(tmp_path)
    home = tmp_path / "hermes"
    cfg = contract(home, repo=repo)
    cfg["remote"] = str(remote)
    write_contract(home, cfg)
    (repo / "delete-me.txt").write_text("delete me\n", encoding="utf-8")
    git(repo, "add", "delete-me.txt")
    git(repo, "commit", "-m", "recovery fixture")
    git(repo, "push", str(remote), "HEAD:main")
    state = Path(cfg["state_dir"])
    run_id = "a" * 32
    job_id = "job-1"
    root = state / "worktrees" / job_id / run_id
    run_dir = state / "runs" / run_id
    root.parent.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    started = datetime.now(timezone.utc).isoformat()
    git(repo, "worktree", "add", "--detach", str(root), base)
    (root / "changed.txt").write_text("failed evidence\n", encoding="utf-8")
    receipt = {
        "success": False,
        "error": "Script exited with code 7",
        "kernel_cleanup": {"local": "ok", "remote": "ok"},
        "descendant_cleanup": {
            "observed": [], "live_count": 0, "survivor_count": 0, "survivors": []
        },
    }
    (run_dir / "result.json").write_text(json.dumps(receipt), encoding="utf-8")
    marker = {
        "version": 1,
        "kind": "owner-job",
        "job": job_id,
        "run": run_id,
        "run_dir": str(run_dir),
        "root": str(root),
        "base": base,
        "pid": 999_999_999,
        "pid_created": 1.0,
        "started": started,
        "intent": {"name": "test", "allowed_paths": ["changed.txt"]},
        "phase": phase,
    }
    if legacy:
        marker = {"job": job_id, "root": str(root), "run": str(run_dir), "base": base}
        receipt.pop("kernel_cleanup")
        (run_dir / "result.json").write_text(json.dumps(receipt), encoding="utf-8")
    pending = state / "pending-owner.json"
    pending.write_text(json.dumps(marker), encoding="utf-8")
    return cfg, repo, remote, state, root, run_dir, run_id, marker


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ("missing-receipt", "receipt"),
        ("bool-survivors", "zero-survivor"),
        ("unknown-survivors", "zero-survivor"),
        ("positive-survivors", "zero-survivor"),
        ("kernel-error", "kernel cleanup"),
        ("publishing", "not safe"),
        ("integrating", "not safe"),
        ("committing", "not safe"),
    ],
)
def test_reconcile_refuses_unproven_completion_and_ambiguous_phases(tmp_path, runner, mutation, expected):
    cfg, _repo, _remote, state, _root, run_dir, run_id, marker = failed_state(tmp_path, runner)
    receipt_path = run_dir / "result.json"
    if mutation == "missing-receipt":
        receipt_path.unlink()
    elif mutation in {"bool-survivors", "unknown-survivors", "positive-survivors"}:
        receipt = json.loads(receipt_path.read_text())
        receipt["descendant_cleanup"]["survivor_count"] = {
            "bool-survivors": False,
            "unknown-survivors": None,
            "positive-survivors": 1,
        }[mutation]
        receipt_path.write_text(json.dumps(receipt))
    elif mutation == "kernel-error":
        receipt = json.loads(receipt_path.read_text())
        receipt["kernel_cleanup"]["remote"] = "RuntimeError"
        receipt_path.write_text(json.dumps(receipt))
    else:
        marker["phase"] = mutation
        if mutation in {"publishing", "integrating"}:
            marker["head"] = marker["base"]
        if mutation == "integrating":
            marker["remote_head"] = marker["head"]
        (state / "pending-owner.json").write_text(json.dumps(marker))

    with pytest.raises(runner.OwnershipError, match=expected) as caught:
        runner.reconcile_pending(cfg, run_id)
    if mutation in {"publishing", "integrating", "committing"}:
        assert "remote_head=" in str(caught.value)
    assert (state / "pending-owner.json").exists()
    assert not (state / "failed" / run_id).exists()


def test_reconcile_refuses_root_symlink_and_live_root_process(tmp_path, runner):
    cfg, _repo, _remote, state, root, _run_dir, run_id, _marker = failed_state(tmp_path, runner)
    (root / "link.txt").symlink_to(tmp_path / "outside")
    with pytest.raises(runner.OwnershipError, match="Symlink"):
        runner.reconcile_pending(cfg, run_id)
    (root / "link.txt").unlink()

    sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=root)
    try:
        with pytest.raises(runner.OwnershipError, match="Processes still reference"):
            runner.reconcile_pending(cfg, run_id)
    finally:
        sleeper.kill()
        sleeper.wait()
    result = runner.reconcile_pending(cfg, run_id)
    assert result["status"] == "archived"


def test_older_readable_process_that_enters_run_root_refuses_reconciliation(tmp_path, runner):
    root = (
        tmp_path / "hermes" / "ownership-state" / "worktrees" / "job-1" / ("a" * 32)
    )
    release = tmp_path / "release"
    entered = tmp_path / "entered"
    launched = tmp_path / "launched"
    script = (
        "import os, pathlib, time\n"
        f"release=pathlib.Path({str(release)!r})\n"
        f"pathlib.Path({str(launched)!r}).write_text('ready')\n"
        "while not release.exists(): time.sleep(0.01)\n"
        f"os.chdir({str(root)!r})\n"
        f"pathlib.Path({str(entered)!r}).write_text('entered')\n"
        "time.sleep(60)\n"
    )
    process = subprocess.Popen([sys.executable, "-c", script])
    try:
        deadline = time.monotonic() + 5
        while not launched.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert launched.exists()
        time.sleep(1.1)  # Older than the scan boundary plus its clock-tick overlap.
        cfg, _repo, _remote, state, actual_root, _run_dir, run_id, _marker = failed_state(
            tmp_path, runner
        )
        assert actual_root == root
        release.write_text("go", encoding="utf-8")
        deadline = time.monotonic() + 5
        while not entered.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert entered.exists()

        with pytest.raises(runner.OwnershipError, match="Processes still reference"):
            runner.reconcile_pending(cfg, run_id)
        assert (state / "pending-owner.json").exists()
    finally:
        process.kill()
        process.wait()


def test_complete_archive_is_revalidated_after_crash_before_marker_move(tmp_path, runner):
    cfg, _repo, _remote, state, root, run_dir, run_id, marker = failed_state(tmp_path, runner)
    (root / "README.md").write_text("staged content\n", encoding="utf-8")
    git(root, "add", "README.md")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    (root / "delete-me.txt").unlink()
    pending = state / "pending-owner.json"
    archive = runner._archive_snapshot(state, pending, marker, run_id, root, run_dir, marker["base"])
    assert pending.exists() and (archive / "manifest.json").exists()
    assert (archive / "tracked.cached.diff").read_bytes()
    assert (archive / "tracked.working.diff").read_bytes()
    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    readme = next(entry for entry in manifest["entries"] if entry["path"] == "README.md")
    deleted = next(entry for entry in manifest["entries"] if entry["path"] == "delete-me.txt")
    assert readme["staged"] is True and readme["unstaged"] is True
    assert deleted["status"] == "deleted" and deleted["unstaged"] is True

    result = runner.reconcile_pending(cfg, run_id)
    assert result["status"] == "archived"
    assert not pending.exists()
    assert (archive / "pending-owner.json").exists()


def test_corrupt_complete_archive_never_clears_marker(tmp_path, runner):
    cfg, _repo, _remote, state, root, run_dir, run_id, marker = failed_state(tmp_path, runner)
    pending = state / "pending-owner.json"
    archive = runner._archive_snapshot(state, pending, marker, run_id, root, run_dir, marker["base"])
    (archive / "files" / "changed.txt").write_text("tampered", encoding="utf-8")

    with pytest.raises(runner.OwnershipError, match="corrupt"):
        runner.reconcile_pending(cfg, run_id)
    assert pending.exists()


def test_legacy_marker_requires_explicit_legacy_reconciliation(tmp_path, runner):
    cfg, _repo, _remote, state, _root, _run_dir, run_id, _marker = failed_state(
        tmp_path, runner, legacy=True
    )
    with pytest.raises(runner.OwnershipError, match="recognized owner-job"):
        runner.reconcile_pending(cfg, run_id)
    assert (state / "pending-owner.json").exists()

    result = runner.reconcile_pending(cfg, run_id, legacy=True)
    assert result["status"] == "archived"


@pytest.mark.parametrize("dangling", [False, True])
def test_reconcile_rejects_active_pending_marker_symlink(tmp_path, runner, dangling):
    cfg, _repo, _remote, state, _root, _run_dir, run_id, _marker = failed_state(tmp_path, runner)
    pending = state / "pending-owner.json"
    original = pending.read_bytes()
    pending.unlink()
    target = tmp_path / "marker-target.json"
    if not dangling:
        target.write_bytes(original)
    pending.symlink_to(target)

    with pytest.raises(runner.OwnershipError, match="symlink"):
        runner.reconcile_pending(cfg, run_id)
    assert pending.is_symlink()
    if not dangling:
        assert target.read_bytes() == original


@pytest.mark.parametrize("dangling", [False, True])
def test_execute_job_rejects_active_pending_marker_symlink_before_overwrite(
    tmp_path, runner, dangling
):
    repo, remote = init_repo(tmp_path)
    home = tmp_path / "hermes"
    cfg = contract(home, repo=repo)
    cfg["remote"] = str(remote)
    write_contract(home, cfg)
    state = Path(cfg["state_dir"])
    state.mkdir(parents=True)
    pending = state / "pending-owner.json"
    target = tmp_path / "marker-target.json"
    if not dangling:
        target.write_text('{"preserve": true}', encoding="utf-8")
    pending.symlink_to(target)
    called = []

    with pytest.raises(runner.OwnershipError, match="symlink"):
        runner.execute_job(
            cfg,
            {"id": "symlink-guard", "allowed_paths": ["result.md"]},
            executor=lambda *_args: called.append(True),
        )
    assert not called
    assert pending.is_symlink()
    if not dangling:
        assert target.read_text(encoding="utf-8") == '{"preserve": true}'


def test_marker_kind_and_exact_paths_are_fail_closed(tmp_path, runner):
    cfg, _repo, _remote, state, _root, _run_dir, run_id, marker = failed_state(tmp_path, runner)
    marker["root"] = str(tmp_path / "outside")
    (state / "pending-owner.json").write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(runner.OwnershipError, match="paths do not match"):
        runner.reconcile_pending(cfg, run_id)

    marker["root"] = str(state / "worktrees" / marker["job"] / run_id)
    marker["kind"] = "contribution"
    (state / "pending-owner.json").write_text(json.dumps(marker), encoding="utf-8")
    with pytest.raises(runner.OwnershipError, match="recognized owner-job"):
        runner.reconcile_pending(cfg, run_id)
    assert (state / "pending-owner.json").exists()


@pytest.mark.parametrize("missing", ["cwd", "cmdline"])
def test_candidate_process_access_uncertainty_is_fail_closed(tmp_path, runner, monkeypatch, missing):
    class Candidate:
        pid = 424242

        @staticmethod
        def uids():
            return type("Uids", (), {"real": os.getuid()})()

        @staticmethod
        def create_time():
            return 2.0

        @staticmethod
        def status():
            return psutil.STATUS_SLEEPING

        @staticmethod
        def cwd():
            if missing == "cwd":
                raise psutil.AccessDenied(Candidate.pid)
            return str(tmp_path)

        @staticmethod
        def cmdline():
            if missing == "cmdline":
                raise psutil.AccessDenied(Candidate.pid)
            return ["python", "worker.py"]

    monkeypatch.setattr(psutil, "process_iter", lambda _attrs: [Candidate()])
    with pytest.raises(runner.OwnershipError, match="fully inspect"):
        runner._root_aware_processes(tmp_path / "root", None, not_before=1.0)


@pytest.mark.parametrize("rooted_surface", ["cwd", "argv"])
def test_preexisting_process_positive_root_evidence_wins_over_other_access_error(
    tmp_path, runner, monkeypatch, rooted_surface
):
    root = tmp_path / "root"

    class Preexisting:
        pid = 434343

        @staticmethod
        def uids():
            return type("Uids", (), {"real": os.getuid()})()

        @staticmethod
        def create_time():
            return 1.0

        @staticmethod
        def status():
            return psutil.STATUS_SLEEPING

        @staticmethod
        def cwd():
            if rooted_surface == "argv":
                raise psutil.AccessDenied(Preexisting.pid)
            return str(root)

        @staticmethod
        def cmdline():
            if rooted_surface == "cwd":
                raise psutil.AccessDenied(Preexisting.pid)
            return ["python", f"--workdir={root}"]

    monkeypatch.setattr(psutil, "process_iter", lambda _attrs: [Preexisting()])
    with pytest.raises(runner.OwnershipError, match="Processes still reference"):
        runner._root_aware_processes(root, None, not_before=10.0)


def test_fully_uninspectable_preexisting_process_is_not_treated_as_a_descendant(
    tmp_path, runner, monkeypatch
):
    class Preexisting:
        pid = 444444

        @staticmethod
        def uids():
            return type("Uids", (), {"real": os.getuid()})()

        @staticmethod
        def create_time():
            return 1.0

        @staticmethod
        def status():
            return psutil.STATUS_SLEEPING

        @staticmethod
        def cwd():
            raise psutil.AccessDenied(Preexisting.pid)

        @staticmethod
        def cmdline():
            raise psutil.AccessDenied(Preexisting.pid)

    monkeypatch.setattr(psutil, "process_iter", lambda _attrs: [Preexisting()])
    runner._root_aware_processes(tmp_path / "root", None, not_before=10.0)


def test_failed_archive_paths_and_manifest_names_reject_symlinks_and_traversal(tmp_path, runner):
    cfg, _repo, _remote, state, _root, _run_dir, run_id, _marker = failed_state(tmp_path, runner)
    outside = tmp_path / "outside-archive"
    outside.mkdir()
    (state / "failed").symlink_to(outside, target_is_directory=True)
    with pytest.raises(runner.OwnershipError, match="Symlink"):
        runner.reconcile_pending(cfg, run_id)
    assert not list(outside.iterdir())
    for name in ("../escape", "/absolute"):
        with pytest.raises(runner.OwnershipError, match="Unsafe"):
            runner._safe_archive_artifact(state, name)


def test_concurrent_reconcilers_serialize_to_one_archive(tmp_path, runner):
    cfg, _repo, _remote, state, _root, _run_dir, run_id, _marker = failed_state(tmp_path, runner)
    env = {**os.environ, "HOME": str(tmp_path / "home"), "HERMES_HOME": cfg["hermes_home"]}
    command = [sys.executable, str(RUNNER), "--reconcile", run_id]
    processes = [
        subprocess.Popen(command, cwd=tmp_path, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=20) + (process.returncode,) for process in processes]
    assert all(returncode == 0 for _stdout, _stderr, returncode in results), results
    statuses = [json.loads(stdout)["status"] for stdout, _stderr, _returncode in results]
    assert sorted(statuses) == ["archived", "no-pending-owner"]
    assert len(list((state / "failed").iterdir())) == 1


def test_publication_intent_is_durable_before_push(tmp_path, runner, monkeypatch):
    repo, remote = init_repo(tmp_path)
    home = tmp_path / "hermes"
    cfg = contract(home, repo=repo)
    cfg["remote"] = str(remote)
    write_contract(home, cfg)
    state = Path(cfg["state_dir"])
    observed = {}
    phases = []
    original_publish = runner.publish
    original_atomic_write = runner._atomic_write_json

    def atomic_write(path, value):
        if Path(path).name == "pending-owner.json":
            phases.append(value["phase"])
        return original_atomic_write(path, value)

    def executor(_job, root, _run_dir):
        (root / "result.md").write_text("published\n", encoding="utf-8")
        return "done"

    def publish(root, contract_value, base):
        marker = json.loads((state / "pending-owner.json").read_text(encoding="utf-8"))
        observed.update(marker)
        return original_publish(root, contract_value, base)

    monkeypatch.setattr(runner, "_atomic_write_json", atomic_write)
    monkeypatch.setattr(runner, "publish", publish)
    assert runner.execute_job(
        cfg, {"id": "journal", "name": "journal test", "allowed_paths": ["result.md"]},
        executor=executor,
    ) == "done"
    assert observed["phase"] == "publishing"
    assert phases == ["prepared", "executing", "validating", "committing", "publishing", "integrating"]
    assert observed["head"] == git(repo, "rev-parse", "HEAD").stdout.strip()
    assert observed["intent"] == {"name": "journal test", "allowed_paths": ["result.md"]}
