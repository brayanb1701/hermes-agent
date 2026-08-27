#!/usr/bin/env python3
"""Tests for the local Calcifer Hermes launcher."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "calcifer_agent.py"
spec = importlib.util.spec_from_file_location("calcifer_agent", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load {MODULE_PATH}")
calcifer_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calcifer_agent)


class NameValidationTests(unittest.TestCase):
    def test_accepts_short_lowercase_hyphenated_name(self) -> None:
        self.assertEqual(calcifer_agent.validate_name("fieldlink-tests"), "fieldlink-tests")

    def test_rejects_names_that_are_unsafe_for_tmux_and_systemd(self) -> None:
        for value in ("Uppercase", "has space", "../escape", "", "a" * 49):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "lowercase"):
                    calcifer_agent.validate_name(value)

    def test_rejects_ssh_option_injection_as_host(self) -> None:
        self.assertEqual(calcifer_agent.validate_host("calcifer-ts"), "calcifer-ts")
        with self.assertRaisesRegex(ValueError, "host"):
            calcifer_agent.validate_host("-oProxyCommand=bad")


class RemoteFailureTests(unittest.TestCase):
    def test_transport_failure_is_not_treated_as_inactive(self) -> None:
        result = subprocess.CompletedProcess(["ssh"], 255, "", "connection failed")
        with self.assertRaisesRegex(RuntimeError, "connection failed"):
            calcifer_agent.raise_on_transport_error(result)

    def test_guarded_mode_fails_closed_if_remote_policy_is_not_deny(self) -> None:
        result = subprocess.CompletedProcess(["ssh"], 0, "approve\n", "")
        with patch.object(calcifer_agent, "ssh", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "requires.*deny"):
                calcifer_agent.require_guarded_policy()

    def test_guarded_mode_accepts_explicit_remote_deny_policy(self) -> None:
        result = subprocess.CompletedProcess(["ssh"], 0, "deny\n", "")
        with patch.object(calcifer_agent, "ssh", return_value=result):
            calcifer_agent.require_guarded_policy()


class SessionPolicyTests(unittest.TestCase):
    def test_reused_session_must_match_requested_trust(self) -> None:
        metadata = {"permission_policy": "trusted-yolo", "workdir": None}
        with self.assertRaisesRegex(RuntimeError, "permission policy"):
            calcifer_agent.require_matching_session(metadata, trusted=False, workdir=None)

    def test_reused_session_must_match_requested_workdir(self) -> None:
        metadata = {"permission_policy": "interactive-approvals", "workdir": "/tmp/a"}
        with self.assertRaisesRegex(RuntimeError, "working directory"):
            calcifer_agent.require_matching_session(metadata, trusted=False, workdir="/tmp/b")


class HermesCommandTests(unittest.TestCase):
    def test_guarded_goal_never_enables_yolo(self) -> None:
        command = calcifer_agent.build_goal_command(
            prompt_path="/home/brayan/.local/state/calcifer-agent/goals/a/prompt.txt",
            budget_seconds=3600,
            trusted=False,
            workdir=None,
        )
        self.assertNotIn("--yolo", command)
        self.assertIn("--query-file", command)
        self.assertIn("--run-budget", command)
        self.assertEqual(command[-2:], ["--source", "calcifer-agent"])

    def test_trusted_goal_is_explicitly_process_scoped(self) -> None:
        command = calcifer_agent.build_goal_command(
            prompt_path="/tmp/prompt.txt",
            budget_seconds=0,
            trusted=True,
            workdir="/home/brayan/projects/example",
        )
        self.assertIn("--yolo", command)
        self.assertNotIn("--run-budget", command)
        self.assertEqual(command[command.index("--in") + 1], "/home/brayan/projects/example")

    def test_interactive_command_uses_same_explicit_trust_policy(self) -> None:
        guarded = calcifer_agent.build_session_command(trusted=False, workdir=None)
        trusted = calcifer_agent.build_session_command(trusted=True, workdir="/tmp/work")
        self.assertNotIn("--yolo", guarded)
        self.assertIn("--yolo", trusted)
        self.assertEqual(trusted[trusted.index("--in") + 1], "/tmp/work")


class BudgetTests(unittest.TestCase):
    def test_parses_human_friendly_budget(self) -> None:
        self.assertEqual(calcifer_agent.parse_budget("90m"), 5400)
        self.assertEqual(calcifer_agent.parse_budget("4h"), 14400)
        self.assertEqual(calcifer_agent.parse_budget("0"), 0)

    def test_rejects_invalid_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "budget"):
            calcifer_agent.parse_budget("tomorrow")


if __name__ == "__main__":
    unittest.main()
