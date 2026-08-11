"""Regression tests for Brayan's daily upstream CI activation step."""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "brayan-personalization/runtime/scripts/hermes_upstream_rebase_ci.py"
)


def load_ci_module():
    spec = importlib.util.spec_from_file_location("brayan_upstream_ci", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_activation_is_required_when_verified_candidate_differs_from_live_head():
    ci = load_ci_module()

    assert ci.live_activation_required("candidate", "live") is True
    assert ci.live_activation_required("same", "same") is False


def test_activation_command_targets_personalization_branch_and_runs_detached():
    ci = load_ci_module()

    cmd = ci.build_live_activation_command("abcdef1234567890")
    rendered = " ".join(cmd)

    assert cmd[:2] == ["systemd-run", "--user"]
    assert "--on-active=5s" in cmd
    assert "hermes-personalization-activate-abcdef123456" in rendered
    assert "update --branch brayan/personal-hermes-customizations --yes --no-backup" in rendered


def test_non_target_live_branch_can_recover_from_remote_candidate(monkeypatch):
    ci = load_ci_module()
    calls = []

    def fake_git(*args, **kwargs):
        calls.append(args)
        if args == ("branch", "--show-current"):
            return {"returncode": 0, "stdout": "main\n", "stderr": ""}
        if args[:2] == ("status", "--porcelain"):
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if args[:2] == ("fetch", "upstream"):
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if args[:2] == ("fetch", "origin"):
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if args == ("rev-parse", "origin/brayan/personal-hermes-customizations"):
            return {"returncode": 0, "stdout": "remote-head\n", "stderr": ""}
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(ci, "git", fake_git)
    monkeypatch.setattr(ci, "dirty_paths", lambda repo: [])

    commands = []
    assert ci.choose_base_ref(commands) == "remote-head"
