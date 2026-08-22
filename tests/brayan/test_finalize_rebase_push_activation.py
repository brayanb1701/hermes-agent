"""Regression tests for the exception-path rebase finalizer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "brayan-personalization/runtime/skills/automation-agents/"
    "hermes-upstream-rebase-ci-agent/scripts/finalize_rebase_push.py"
)


def load_finalizer():
    spec = importlib.util.spec_from_file_location("brayan_rebase_finalizer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_repo_accepts_only_live_or_ci_worktree():
    finalizer = load_finalizer()

    assert finalizer.resolve_candidate_repo(str(finalizer.LIVE_REPO)) == finalizer.LIVE_REPO
    assert finalizer.resolve_candidate_repo(str(finalizer.WORKTREE)) == finalizer.WORKTREE
    with pytest.raises(ValueError):
        finalizer.resolve_candidate_repo("/tmp/untrusted-repo")


def test_finalizer_activation_command_uses_verified_personalization_branch():
    finalizer = load_finalizer()

    command = finalizer.build_live_activation_command("abcdef1234567890")
    rendered = " ".join(command)

    assert command[:2] == ["systemd-run", "--user"]
    assert "--on-active=5s" in command
    assert "hermes-personalization-activate-abcdef123456" in rendered
    assert "update --branch second-computer-evolution --yes --no-backup" in rendered
