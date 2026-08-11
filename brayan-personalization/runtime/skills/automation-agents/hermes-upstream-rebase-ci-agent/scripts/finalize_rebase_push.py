#!/usr/bin/env python3
"""Guarded finalizer for Brayan's Hermes personalization rebase repair.

This script is intentionally narrow. It gives the Hermes upstream-rebase
exception agent one deterministic post-repair capability: after a human/agent
has resolved conflicts and left the candidate repo clean, verify the branch,
push only Brayan's personalization branch with an exact force-with-lease, then
schedule branch-safe activation in the live checkout.

It must not become a generic git helper. Repo, branch, and remotes are hard-coded
by design.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIVE_REPO = Path("/home/brayan/.hermes/hermes-agent")
WORKTREE = Path("/home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci")
REPO = LIVE_REPO
TARGET_BRANCH = "brayan/personal-hermes-customizations"
TARGET_REF = f"refs/heads/{TARGET_BRANCH}"
ORIGIN_REMOTE = "origin"
UPSTREAM_REMOTE = "upstream"
PYTHON = LIVE_REPO / "venv/bin/python"
HERMES = Path("/home/brayan/.local/bin/hermes")

EXPECTED_ORIGIN_HINTS = (
    "github.com:brayanb1701/hermes-agent.git",
    "github.com/brayanb1701/hermes-agent.git",
)
EXPECTED_UPSTREAM_HINTS = (
    "github.com:NousResearch/hermes-agent.git",
    "github.com/NousResearch/hermes-agent.git",
)

TEST_COMMANDS = [
    {
        "name": "py_compile_finalizer_and_personalization_scripts",
        "cmd": [
            str(PYTHON),
            "-m",
            "py_compile",
            str(Path(__file__).resolve()),
            "scripts/sync-brayan-personalization.py",
            "scripts/apply-brayan-personalization.py",
        ],
        "timeout": 120,
    },
    {
        "name": "focused_wake_gate_and_intake_tests",
        "cmd": [
            str(PYTHON),
            "-m",
            "pytest",
            "tests/gateway/test_notes_intake_pipeline.py",
            "tests/plugins/test_notes_preprocessor_intake.py",
            "tests/cron/test_cron_script.py::TestScriptWakeGate",
            "-q",
            "-o",
            "addopts=",
        ],
        "timeout": 600,
    },
    {
        "name": "cron_tooling_tests",
        "cmd": [
            str(PYTHON),
            "-m",
            "pytest",
            "tests/cron/test_cron_script.py",
            "tests/tools/test_cronjob_tools.py",
            "tests/hermes_cli/test_cron.py",
            "-q",
            "-o",
            "addopts=",
        ],
        "timeout": 600,
    },
    {
        "name": "hermes_config_check",
        "cmd": [str(PYTHON), "-m", "hermes_cli.main", "config", "check"],
        "timeout": 180,
    },
]

SENSITIVE_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
    "gho_",
    "ghp_",
    "glpat-",
    "oauth",
    "password",
    "private_key",
    "secret",
    "sk-",
    "token",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_candidate_repo(value: str) -> Path:
    """Accept only the hard-coded live checkout or isolated CI worktree."""
    candidate = Path(value).expanduser().resolve()
    allowed = {LIVE_REPO.resolve(), WORKTREE.resolve()}
    if candidate not in allowed:
        raise ValueError(f"candidate repo must be {LIVE_REPO} or {WORKTREE}")
    return candidate


def build_live_activation_command(candidate_head: str) -> list[str]:
    unit = f"hermes-personalization-activate-{candidate_head[:12]}"
    return [
        "systemd-run",
        "--user",
        "--collect",
        "--on-active=5s",
        f"--unit={unit}",
        "--property=TimeoutStartSec=1800",
        str(HERMES),
        "update",
        "--branch",
        TARGET_BRANCH,
        "--yes",
        "--no-backup",
    ]


def schedule_live_activation(candidate_head: str, commands: list[dict[str, Any]]) -> bool:
    live_head_result = run(["git", "rev-parse", "HEAD"], cwd=LIVE_REPO)
    commands.append(live_head_result)
    if not ok_cmd(live_head_result):
        fail("activation_preflight", "Could not resolve live checkout HEAD.", commands=commands)
    if stdout(live_head_result) == candidate_head:
        return False

    scheduled = run(build_live_activation_command(candidate_head), timeout=120, cwd=LIVE_REPO)
    commands.append(scheduled)
    if not ok_cmd(scheduled):
        fail(
            "activation_schedule_failed",
            "Candidate was verified/pushed, but detached live activation could not be scheduled.",
            commands=commands,
        )
    return True


def redact(text: str, limit: int = 8000) -> str:
    if not text:
        return ""
    redacted_lines: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if any(marker in lower for marker in SENSITIVE_MARKERS):
            redacted_lines.append("[REDACTED SENSITIVE-LOOKING LINE]")
        else:
            redacted_lines.append(line)
    out = "\n".join(redacted_lines)
    if len(out) > limit:
        return out[:limit] + "\n[TRUNCATED]"
    return out


def run(cmd: list[str], *, timeout: int = 300, cwd: Path | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "cmd": cmd,
        "cwd": str(cwd or REPO),
        "timeout": timeout,
    }
    env = {
        **os.environ,
        "NO_COLOR": "1",
        "GIT_EDITOR": "true",
        "GIT_SEQUENCE_EDITOR": "true",
    }
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or REPO,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        record.update(
            {
                "returncode": proc.returncode,
                "stdout": redact(proc.stdout),
                "stderr": redact(proc.stderr),
            }
        )
    except subprocess.TimeoutExpired as exc:
        record.update(
            {
                "returncode": None,
                "timed_out": True,
                "stdout": redact(exc.stdout or ""),
                "stderr": redact(exc.stderr or ""),
            }
        )
    except Exception as exc:  # defensive: JSON diagnostics even on unexpected errors
        record.update(
            {
                "returncode": None,
                "exception": type(exc).__name__,
                "stderr": redact(str(exc)),
            }
        )
    return record


def git(*args: str, timeout: int = 300) -> dict[str, Any]:
    return run(["git", *args], timeout=timeout)


def ok_cmd(result: dict[str, Any]) -> bool:
    return result.get("returncode") == 0


def stdout(result: dict[str, Any]) -> str:
    return (result.get("stdout") or "").strip()


def emit(payload: dict[str, Any], *, exit_code: int = 0) -> None:
    payload.setdefault("timestamp", now())
    payload.setdefault("repo", str(REPO))
    payload.setdefault("target_branch", TARGET_BRANCH)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    raise SystemExit(exit_code)


def fail(stage: str, message: str, *, commands: list[dict[str, Any]] | None = None, **extra: Any) -> None:
    payload = {
        "ok": False,
        "stage": stage,
        "message": message,
        "commands": commands or [],
        "next_action": extra.pop("next_action", "Inspect the stage/message/commands fields, repair the repo state, then rerun this finalizer."),
    }
    payload.update(extra)
    emit(payload, exit_code=1)


def ensure_repo(commands: list[dict[str, Any]]) -> None:
    if not REPO.exists():
        fail("preflight", f"Repo path does not exist: {REPO}")
    if not PYTHON.exists():
        fail("preflight", f"Repo venv Python does not exist: {PYTHON}")
    inside = git("rev-parse", "--is-inside-work-tree")
    commands.append(inside)
    if not ok_cmd(inside) or stdout(inside) != "true":
        fail("preflight", "Target path is not a Git working tree.", commands=commands)


def git_path(path_name: str, commands: list[dict[str, Any]]) -> Path:
    result = git("rev-parse", "--git-path", path_name)
    commands.append(result)
    if not ok_cmd(result):
        fail("preflight", f"Could not resolve git path {path_name}.", commands=commands)
    return REPO / stdout(result)


def command_stdout(cmd: dict[str, Any], stage: str, label: str, commands: list[dict[str, Any]]) -> str:
    commands.append(cmd)
    if not ok_cmd(cmd):
        fail(stage, f"Failed to read {label}.", commands=commands)
    return stdout(cmd)


def remote_url(remote: str, commands: list[dict[str, Any]]) -> str:
    return command_stdout(git("remote", "get-url", remote), "preflight", f"remote URL for {remote}", commands)


def contains_any(value: str, hints: tuple[str, ...]) -> bool:
    return any(hint in value for hint in hints)


def is_ancestor(ancestor: str, descendant: str, commands: list[dict[str, Any]]) -> bool:
    result = git("merge-base", "--is-ancestor", ancestor, descendant)
    commands.append(result)
    return ok_cmd(result)


def collect_snapshot(commands: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    local_commands: list[dict[str, Any]] = [] if commands is None else commands

    def maybe(cmd: dict[str, Any]) -> str:
        local_commands.append(cmd)
        return stdout(cmd) if ok_cmd(cmd) else ""

    return {
        "branch": maybe(git("branch", "--show-current")),
        "head": maybe(git("rev-parse", "--short", "HEAD")),
        "head_full": maybe(git("rev-parse", "HEAD")),
        "status_short": maybe(git("status", "--short", "--branch")),
        "upstream_main": maybe(git("rev-parse", "--short", "upstream/main")),
        "origin_target": maybe(git("rev-parse", "--short", f"origin/{TARGET_BRANCH}")),
    }


def preflight_and_fetch(commands: list[dict[str, Any]]) -> dict[str, Any]:
    ensure_repo(commands)

    # Refuse in-progress Git operations before fetching or testing.
    in_progress: list[str] = []
    for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
        marker_path = git_path(marker, commands)
        if marker_path.exists():
            in_progress.append(str(marker_path))
    if in_progress:
        fail(
            "git_operation_in_progress",
            "A Git rebase/merge operation is still in progress; finish or abort it before finalizing.",
            commands=commands,
            in_progress=in_progress,
            next_action="Resolve remaining conflicts, run `GIT_EDITOR=true git rebase --continue` if appropriate, then rerun this finalizer.",
        )

    branch = command_stdout(git("branch", "--show-current"), "preflight", "current branch", commands)
    if REPO == LIVE_REPO and branch != TARGET_BRANCH:
        fail(
            "wrong_branch",
            f"Expected current branch {TARGET_BRANCH!r}, found {branch or '[detached]'}.",
            commands=commands,
            current_branch=branch,
            next_action=f"Switch to {TARGET_BRANCH} or finalize the repaired CI worktree with --repo {WORKTREE}.",
        )

    origin_url = remote_url(ORIGIN_REMOTE, commands)
    upstream_url = remote_url(UPSTREAM_REMOTE, commands)
    if not contains_any(origin_url, EXPECTED_ORIGIN_HINTS):
        fail(
            "wrong_origin_remote",
            "Origin remote is not Brayan's Hermes fork; refusing to push.",
            commands=commands,
            origin_url=origin_url,
            expected_hints=EXPECTED_ORIGIN_HINTS,
        )
    if not contains_any(upstream_url, EXPECTED_UPSTREAM_HINTS):
        fail(
            "wrong_upstream_remote",
            "Upstream remote is not the official NousResearch Hermes repo; refusing to push.",
            commands=commands,
            upstream_url=upstream_url,
            expected_hints=EXPECTED_UPSTREAM_HINTS,
        )

    status = command_stdout(git("status", "--porcelain"), "preflight", "working tree status", commands)
    if status:
        fail(
            "dirty_working_tree",
            "Working tree has uncommitted changes; refusing final push.",
            commands=commands,
            dirty_status=status,
            next_action="Commit or intentionally discard the listed changes, then rerun this finalizer.",
        )

    fetch_upstream = git("fetch", UPSTREAM_REMOTE, "main", "--quiet", timeout=180)
    commands.append(fetch_upstream)
    if not ok_cmd(fetch_upstream):
        fail("fetch_upstream", "Failed to fetch upstream/main.", commands=commands)

    fetch_origin = git("fetch", ORIGIN_REMOTE, TARGET_BRANCH, "--quiet", timeout=180)
    commands.append(fetch_origin)
    if not ok_cmd(fetch_origin):
        fail("fetch_origin", f"Failed to fetch origin/{TARGET_BRANCH}.", commands=commands)

    snapshot_commands: list[dict[str, Any]] = []
    snapshot = collect_snapshot(snapshot_commands)
    commands.extend(snapshot_commands)

    head_full = snapshot.get("head_full") or command_stdout(git("rev-parse", "HEAD"), "preflight", "HEAD", commands)
    origin_full = command_stdout(git("rev-parse", f"origin/{TARGET_BRANCH}"), "preflight", f"origin/{TARGET_BRANCH}", commands)
    upstream_full = command_stdout(git("rev-parse", "upstream/main"), "preflight", "upstream/main", commands)

    if not is_ancestor("upstream/main", "HEAD", commands):
        fail(
            "missing_upstream_main",
            "Local personalization branch does not contain upstream/main; refusing to push stale branch.",
            commands=commands,
            snapshot=snapshot,
            next_action="Rebase the personalization branch onto upstream/main, resolve conflicts, verify, then rerun this finalizer.",
        )

    return {
        "snapshot": snapshot,
        "head_full": head_full,
        "origin_full": origin_full,
        "upstream_full": upstream_full,
        "origin_url": origin_url,
        "upstream_url": upstream_url,
    }


def run_verification(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in TEST_COMMANDS:
        result = run(item["cmd"], timeout=item["timeout"])
        commands.append(result)
        check = {
            "name": item["name"],
            "ok": ok_cmd(result),
            "returncode": result.get("returncode"),
        }
        checks.append(check)
        if not ok_cmd(result):
            fail(
                "verification_failed",
                f"Verification step failed: {item['name']}.",
                commands=commands,
                checks=checks,
                failed_check=item["name"],
                next_action="Use the failed command output to fix tests/config, then rerun this finalizer.",
            )
    return checks


def main() -> None:
    global REPO

    parser = argparse.ArgumentParser(description="Guarded final push for Brayan's Hermes personalization rebase repair.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Run verification, push with an exact force-with-lease, and schedule live activation.")
    mode.add_argument("--check", action="store_true", help="Run all guards and verification, but do not push or activate.")
    parser.add_argument(
        "--repo",
        default=str(LIVE_REPO),
        help=f"Candidate checkout to verify: {LIVE_REPO} or {WORKTREE}.",
    )
    parser.add_argument("--no-fetch", action="store_true", help="Reserved for debugging only; currently refused to keep leases fresh.")
    args = parser.parse_args()

    try:
        REPO = resolve_candidate_repo(args.repo)
    except ValueError as exc:
        fail("invalid_candidate_repo", str(exc))

    if args.no_fetch:
        fail("unsupported_option", "--no-fetch is intentionally refused; the finalizer must fetch before computing the exact lease.")

    run_mode = "apply" if args.apply else ("check" if args.check else "dry_run")
    commands: list[dict[str, Any]] = []

    data = preflight_and_fetch(commands)
    head_full = data["head_full"]
    origin_full = data["origin_full"]

    push_command = [
        "git",
        "push",
        f"--force-with-lease={TARGET_REF}:{origin_full}",
        ORIGIN_REMOTE,
        f"HEAD:{TARGET_REF}",
    ]

    checks: list[dict[str, Any]] = []
    if args.apply or args.check:
        checks = run_verification(commands)

    if head_full == origin_full:
        activation_scheduled = schedule_live_activation(head_full, commands) if args.apply else False
        emit(
            {
                "ok": True,
                "mode": run_mode,
                "stage": "activated" if activation_scheduled else "no_op",
                "message": (
                    f"origin/{TARGET_BRANCH} already matched the verified candidate; detached live activation scheduled."
                    if activation_scheduled
                    else f"origin/{TARGET_BRANCH} already matches candidate HEAD; no push needed."
                ),
                "pushed": False,
                "activation_scheduled": activation_scheduled,
                "snapshot": data["snapshot"],
                "origin_before": origin_full,
                "head": head_full,
                "checks": checks,
                "commands": commands,
            }
        )

    if not args.apply:
        emit(
            {
                "ok": True,
                "mode": run_mode,
                "stage": "ready_to_push" if run_mode == "check" else "dry_run_ready",
                "message": (
                    "Guards passed and verification passed; rerun with --apply to push."
                    if run_mode == "check"
                    else "Guards passed. Dry-run did not run tests or push; rerun with --check to test or --apply to test and push."
                ),
                "pushed": False,
                "planned_push_command": push_command,
                "snapshot": data["snapshot"],
                "origin_before": origin_full,
                "head": head_full,
                "checks": checks,
                "commands": commands,
            }
        )

    push = run(push_command, timeout=240)
    commands.append(push)
    if not ok_cmd(push):
        fail(
            "push_failed",
            "Exact force-with-lease push failed. The remote may have changed after fetch, auth may have failed, or Git rejected the update.",
            commands=commands,
            checks=checks,
            attempted_push_command=push_command,
            origin_before=origin_full,
            head=head_full,
            next_action="Inspect push stderr. If the remote changed, rerun the finalizer after fetching/reviewing the new remote state; do not use a broader force push.",
        )

    verify_origin = git("rev-parse", f"origin/{TARGET_BRANCH}")
    commands.append(verify_origin)
    # The local remote-tracking ref may not update after push without fetch; fetch it.
    fetch_verify = git("fetch", ORIGIN_REMOTE, TARGET_BRANCH, "--quiet", timeout=180)
    commands.append(fetch_verify)
    if not ok_cmd(fetch_verify):
        fail(
            "post_push_fetch_failed",
            "Push succeeded, but fetching origin afterward failed; remote state could not be verified locally.",
            commands=commands,
            checks=checks,
            pushed=True,
        )
    origin_after = command_stdout(git("rev-parse", f"origin/{TARGET_BRANCH}"), "post_push_verify", f"origin/{TARGET_BRANCH}", commands)
    if origin_after != head_full:
        fail(
            "post_push_verify_failed",
            "Push command returned success, but origin remote-tracking ref does not match HEAD after fetch.",
            commands=commands,
            checks=checks,
            pushed=True,
            origin_before=origin_full,
            origin_after=origin_after,
            head=head_full,
        )

    activation_scheduled = schedule_live_activation(head_full, commands)

    emit(
        {
            "ok": True,
            "mode": run_mode,
            "stage": "pushed_and_activation_scheduled" if activation_scheduled else "pushed",
            "message": (
                f"Verified and pushed {TARGET_BRANCH} with exact force-with-lease; detached live activation scheduled."
                if activation_scheduled
                else f"Verified and pushed {TARGET_BRANCH} with exact force-with-lease; live checkout already matched."
            ),
            "pushed": True,
            "activation_scheduled": activation_scheduled,
            "origin_before": origin_full,
            "origin_after": origin_after,
            "head": head_full,
            "checks": checks,
            "snapshot": data["snapshot"],
            "commands": commands,
        }
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        emit(
            {
                "ok": False,
                "stage": "unexpected_exception",
                "message": redact(f"{type(exc).__name__}: {exc}"),
                "next_action": "Inspect the exception, fix the finalizer or environment, then rerun.",
            },
            exit_code=1,
        )
