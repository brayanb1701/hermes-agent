#!/usr/bin/env python3
"""Launch persistent Hermes sessions and detached goals on Calcifer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Sequence


_HOST_RAW = os.environ.get("CALCIFER_AGENT_HOST", "calcifer")
REMOTE_HERMES = "/home/brayan/.local/bin/hermes"
REMOTE_STATE = "/home/brayan/.local/state/calcifer-agent"
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$")
DEFAULT_BUDGET = "4h"


def validate_name(value: str) -> str:
    """Return a safe tmux/systemd identifier or raise ValueError."""
    if not NAME_RE.fullmatch(value):
        raise ValueError(
            "name must be 1-48 lowercase letters, numbers, or hyphens "
            "and must start/end with a letter or number"
        )
    return value


def validate_host(value: str) -> str:
    """Reject SSH option injection while allowing ordinary aliases/FQDNs."""
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,252}[A-Za-z0-9])?", value):
        raise ValueError("host must be a plain SSH alias or hostname, not an option")
    return value


HOST = _HOST_RAW


def parse_budget(value: str) -> int:
    """Parse seconds or a duration ending in s, m, h, or d."""
    match = re.fullmatch(r"([0-9]+)([smhd]?)", value.strip().lower())
    if not match:
        raise ValueError("budget must be seconds or a duration such as 90m, 4h, or 1d")
    amount = int(match.group(1))
    multiplier = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}[match.group(2)]
    return amount * multiplier


def build_goal_command(
    *,
    prompt_path: str,
    budget_seconds: int,
    trusted: bool,
    workdir: str | None,
    reasoning: str | None = None,
) -> list[str]:
    """Build the process-scoped Hermes command for a detached goal."""
    command = [REMOTE_HERMES, "chat", "--query-file", prompt_path, "--quiet"]
    if workdir:
        command.extend(["--in", workdir])
    if budget_seconds:
        command.extend(["--run-budget", str(budget_seconds)])
    if reasoning:
        command.extend(["--reasoning", reasoning])
    if trusted:
        command.append("--yolo")
    command.extend(["--source", "calcifer-agent"])
    return command


def build_session_command(*, trusted: bool, workdir: str | None) -> list[str]:
    """Build the Hermes command for a reconnectable tmux session."""
    command = [REMOTE_HERMES]
    if workdir:
        command.extend(["--in", workdir])
    if trusted:
        command.append("--yolo")
    return command


def _remote_command(arguments: Sequence[str]) -> str:
    return shlex.join(list(arguments))


def raise_on_transport_error(result: subprocess.CompletedProcess[str]) -> None:
    """Distinguish an unreachable SSH peer from a valid negative probe."""
    if result.returncode == 255:
        detail = (result.stderr or result.stdout or "SSH transport failed").strip()
        raise RuntimeError(f"Calcifer SSH connection failed: {detail}")


def ssh(
    arguments: Sequence[str],
    *,
    tty: bool = False,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one safely quoted command on Calcifer."""
    command = ["ssh"]
    if tty:
        command.append("-t")
    command.extend([HOST, _remote_command(arguments)])
    result = subprocess.run(command, check=False, text=True, capture_output=capture)
    raise_on_transport_error(result)
    if check and result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def require_guarded_policy() -> None:
    """Fail closed unless Calcifer's one-shot policy explicitly denies risk."""
    result = ssh(
        [REMOTE_HERMES, "config", "get", "approvals.single_query_mode"],
        capture=True,
    )
    if result.stdout.strip().lower() != "deny":
        raise RuntimeError(
            "guarded mode requires Calcifer approvals.single_query_mode=deny; "
            "use a tmux session for interactive approvals or explicitly pass --trusted"
        )


def require_matching_session(
    metadata: dict[str, object], *, trusted: bool, workdir: str | None
) -> None:
    """Prevent silently reusing a tmux session with different trust/scope."""
    expected = "trusted-yolo" if trusted else "interactive-approvals"
    if metadata.get("permission_policy") != expected:
        raise RuntimeError(
            "existing session permission policy does not match this request; "
            "attach it as-is or stop it before changing trust"
        )
    if metadata.get("workdir") != workdir:
        raise RuntimeError(
            "existing session working directory does not match this request; "
            "attach it as-is or use another name"
        )


def _is_remote_active(unit: str) -> bool:
    result = ssh(
        ["systemctl", "--user", "is-active", "--quiet", unit],
        check=False,
        capture=True,
    )
    return result.returncode == 0


def _tmux_exists(session: str) -> bool:
    result = ssh(["tmux", "has-session", "-t", session], check=False, capture=True)
    return result.returncode == 0


def _copy_private(local_path: Path, remote_path: str) -> None:
    subprocess.run(["scp", "-q", str(local_path), f"{HOST}:{remote_path}"], check=True)
    ssh(["chmod", "600", remote_path])


def _write_remote_json(remote_path: str, value: dict[str, object]) -> None:
    with tempfile.TemporaryDirectory(prefix="calcifer-agent-") as tmp:
        local_path = Path(tmp) / "metadata.json"
        local_path.write_text(json.dumps(value, indent=2) + "\n")
        os.chmod(local_path, 0o600)
        _copy_private(local_path, remote_path)


def _read_remote_json(remote_path: str) -> dict[str, object] | None:
    code = (
        "import pathlib,sys; p=pathlib.Path(sys.argv[1]); "
        "sys.exit(4) if not p.exists() else print(p.read_text())"
    )
    result = ssh(["python3", "-c", code, remote_path], check=False, capture=True)
    if result.returncode == 4:
        return None
    if result.returncode:
        raise RuntimeError(f"could not read remote metadata: {result.stderr.strip()}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid remote metadata at {remote_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"invalid remote metadata at {remote_path}: expected an object")
    return value


def command_run(args: argparse.Namespace) -> int:
    name = validate_name(args.name)
    budget = parse_budget(args.budget)
    unit = f"calcifer-hermes-goal-{name}.service"
    goal_dir = f"{REMOTE_STATE}/goals/{name}"
    prompt_path = f"{goal_dir}/prompt.txt"
    metadata_path = f"{goal_dir}/metadata.json"

    if _is_remote_active(unit):
        raise RuntimeError(f"goal {name!r} is already active; use status, logs, or stop")

    if not args.trusted:
        require_guarded_policy()

    if args.file and args.goal:
        raise ValueError("use either positional goal text or --file, not both")
    if args.file:
        prompt = Path(args.file).expanduser().read_text()
    elif args.goal:
        prompt = " ".join(args.goal)
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        raise ValueError("provide a goal as text, with --file, or through stdin")
    if not prompt.strip():
        raise ValueError("goal cannot be empty")

    ssh(["install", "-d", "-m", "700", goal_dir])
    metadata = {
        "name": name,
        "mode": "systemd-goal",
        "permission_policy": "trusted-yolo" if args.trusted else "guarded-deny",
        "budget_seconds": budget,
        "workdir": args.workdir,
        "reasoning": args.reasoning,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "unit": unit,
    }
    with tempfile.TemporaryDirectory(prefix="calcifer-agent-") as tmp:
        prompt_local = Path(tmp) / "prompt.txt"
        metadata_local = Path(tmp) / "metadata.json"
        prompt_local.write_text(prompt)
        metadata_local.write_text(json.dumps(metadata, indent=2) + "\n")
        os.chmod(prompt_local, 0o600)
        os.chmod(metadata_local, 0o600)
        _copy_private(prompt_local, prompt_path)
        _copy_private(metadata_local, metadata_path)

    hermes_command = build_goal_command(
        prompt_path=prompt_path,
        budget_seconds=budget,
        trusted=args.trusted,
        workdir=args.workdir,
        reasoning=args.reasoning,
    )
    systemd_command = [
        "systemd-run",
        "--user",
        f"--unit={unit.removesuffix('.service')}",
        f"--description=Hermes goal: {name}",
        "--collect",
        "--property=KillMode=mixed",
        "--property=TimeoutStopSec=30",
    ]
    if budget:
        systemd_command.append(f"--property=RuntimeMaxSec={budget}")
    systemd_command.extend(hermes_command)
    ssh(systemd_command)

    policy = "TRUSTED (--yolo, process-scoped)" if args.trusted else "GUARDED (dangerous operations denied)"
    print(f"Started Calcifer goal: {name}")
    print(f"Permission policy: {policy}")
    print(f"Budget: {'unlimited' if budget == 0 else str(budget) + ' seconds'}")
    print(f"Status: calcifer-agent status {name}")
    print(f"Logs:   calcifer-agent logs {name} --follow")
    print(f"Stop:   calcifer-agent stop {name} --goal")
    return 0


def command_session(args: argparse.Namespace) -> int:
    name = validate_name(args.name)
    session = f"calcifer-hermes-session-{name}"
    session_dir = f"{REMOTE_STATE}/sessions/{name}"
    metadata_path = f"{session_dir}/metadata.json"
    if not _tmux_exists(session):
        command = build_session_command(trusted=args.trusted, workdir=args.workdir)
        ssh(["tmux", "new-session", "-d", "-s", session, "-x", "140", "-y", "45", *command])
        metadata = {
            "name": name,
            "mode": "tmux-session",
            "permission_policy": "trusted-yolo" if args.trusted else "interactive-approvals",
            "workdir": args.workdir,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tmux_session": session,
        }
        try:
            ssh(["install", "-d", "-m", "700", session_dir])
            _write_remote_json(metadata_path, metadata)
        except Exception:
            ssh(["tmux", "kill-session", "-t", session], check=False)
            raise
        policy = "trusted --yolo" if args.trusted else "Calcifer's normal smart/manual approvals"
        print(f"Started tmux session {name!r} with {policy}.")
    else:
        metadata = _read_remote_json(metadata_path)
        if metadata is None:
            raise RuntimeError(
                f"existing tmux session {name!r} has no helper metadata; "
                "attach it directly or stop it before helper-managed reuse"
            )
        require_matching_session(metadata, trusted=args.trusted, workdir=args.workdir)
        print(f"Reusing tmux session {name!r}.")

    if args.detach or not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(f"Attach: calcifer-agent attach {name}")
        print("Detach without stopping Hermes: Ctrl-b, then d")
        return 0
    return ssh(["tmux", "attach-session", "-t", session], tty=True, check=False).returncode


def command_attach(args: argparse.Namespace) -> int:
    name = validate_name(args.name)
    session = f"calcifer-hermes-session-{name}"
    if not _tmux_exists(session):
        raise RuntimeError(f"tmux session {name!r} does not exist")
    return ssh(["tmux", "attach-session", "-t", session], tty=True, check=False).returncode


def command_list(_: argparse.Namespace) -> int:
    print("Interactive tmux sessions:")
    tmux_result = ssh(["tmux", "list-sessions"], check=False, capture=True)
    lines = [
        f"  {line}"
        for line in tmux_result.stdout.splitlines()
        if line.startswith("calcifer-hermes-session-")
    ]
    print("\n".join(lines) if lines else "  (none)")

    print("Detached systemd goals:")
    systemd_result = ssh(
        [
            "systemctl",
            "--user",
            "list-units",
            "calcifer-hermes-goal-*",
            "--all",
            "--no-legend",
            "--plain",
        ],
        check=False,
        capture=True,
    )
    output = systemd_result.stdout.strip()
    print(output if output else "  (no active/loaded units)")
    history_code = (
        "import json,pathlib,sys; root=pathlib.Path(sys.argv[1]); "
        "items=[]; "
        "[(items.append(json.loads(p.read_text()))) for p in root.glob('*/metadata.json')]; "
        "[print(f\"  {x['name']}: {x['permission_policy']}, created {x['created_at']}\") "
        "for x in sorted(items,key=lambda v:v.get('created_at',''),reverse=True)[:10]]"
    )
    history = ssh(
        ["python3", "-c", history_code, f"{REMOTE_STATE}/goals"],
        check=False,
        capture=True,
    ).stdout.rstrip()
    print("Recent goal metadata:")
    print(history if history else "  (none)")
    return 0


def command_status(args: argparse.Namespace) -> int:
    name = validate_name(args.name)
    session = f"calcifer-hermes-session-{name}"
    unit = f"calcifer-hermes-goal-{name}.service"
    tmux_active = _tmux_exists(session)
    print(f"Interactive session: {'active' if tmux_active else 'not active'}", flush=True)
    if tmux_active:
        ssh(["tmux", "list-sessions", "-F", "#{session_name}: #{session_attached} attached", "-f", f"#{{==:#{{session_name}},{session}}}"], check=False)
        session_metadata = _read_remote_json(f"{REMOTE_STATE}/sessions/{name}/metadata.json")
        print(
            json.dumps(session_metadata, indent=2) if session_metadata else "  (unmanaged: no helper metadata)",
            flush=True,
        )
    print("Detached goal:", flush=True)
    if _is_remote_active(unit):
        ssh(
            [
                "systemctl",
                "--user",
                "status",
                unit,
                "--no-pager",
                "--lines=8",
            ],
            check=False,
        )
    else:
        print("  not active (it may be completed; inspect logs)", flush=True)
    metadata = f"{REMOTE_STATE}/goals/{name}/metadata.json"
    ssh(["python3", "-c", "import pathlib; p=pathlib.Path(__import__('sys').argv[1]); print(p.read_text() if p.exists() else '(no metadata)')", metadata], check=False)
    return 0


def command_logs(args: argparse.Namespace) -> int:
    name = validate_name(args.name)
    if args.lines < 0:
        raise ValueError("--lines must be nonnegative")
    unit = f"calcifer-hermes-goal-{name}.service"
    command = [
        "journalctl",
        "--user",
        "-u",
        unit,
        "--no-pager",
        "--output=cat",
        f"--lines={args.lines}",
    ]
    if args.follow:
        command.append("--follow")
    return ssh(command, tty=args.follow, check=False).returncode


def command_stop(args: argparse.Namespace) -> int:
    name = validate_name(args.name)
    session = f"calcifer-hermes-session-{name}"
    unit = f"calcifer-hermes-goal-{name}.service"
    stopped = False
    if args.goal or not args.session:
        if _is_remote_active(unit):
            ssh(["systemctl", "--user", "stop", unit])
            print(f"Stopped detached goal {name!r}.")
            stopped = True
    if args.session or not args.goal:
        if _tmux_exists(session):
            ssh(["tmux", "kill-session", "-t", session])
            print(f"Stopped interactive session {name!r}.")
            stopped = True
    if not stopped:
        print(f"No active Calcifer goal/session named {name!r}.")
    return 0


def command_permissions(_: argparse.Namespace) -> int:
    print("Calcifer's persisted approval configuration:")
    for key in ("approvals.mode", "approvals.single_query_mode", "approvals.timeout"):
        result = ssh([REMOTE_HERMES, "config", "get", key], check=False, capture=True)
        print(f"  {key}: {result.stdout.strip() or '(unset)'}")
    print("\nPolicies exposed by this helper:")
    print("  session (default): smart/manual approvals; reattach if Hermes waits")
    print("  session --trusted: process-scoped --yolo; no ordinary approval prompts")
    print("  run (default): guarded one-shot; dangerous operations are denied, never prompted")
    print("  run --trusted: process-scoped --yolo; no ordinary approval prompts")
    print("  Hermes hardline catastrophic-command blocks still apply under --trusted.")
    return 0


def command_doctor(_: argparse.Namespace) -> int:
    probe = [
        "set -eu; "
        "printf 'host='; hostname; "
        "printf 'hermes='; /home/brayan/.local/bin/hermes --version | sed -n '1p'; "
        "printf 'tmux='; tmux -V; "
        "printf 'systemd_user='; systemctl --user is-system-running; "
        "printf 'linger='; loginctl show-user \"$(id -un)\" -p Linger --value"
    ]
    return ssh(["sh", "-c", probe[0]], check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="calcifer-agent",
        description="Run reconnectable or detached Hermes work on Calcifer over Tailscale.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    session = subparsers.add_parser("session", aliases=["tmux"], help="start/reattach a persistent tmux Hermes session")
    session.add_argument("name")
    session.add_argument("--detach", action="store_true", help="start without attaching")
    session.add_argument("--trusted", action="store_true", help="process-scoped --yolo; bypass ordinary approvals")
    session.add_argument("--workdir", help="remote working directory")
    session.set_defaults(func=command_session)

    attach = subparsers.add_parser("attach", help="attach to an existing tmux session")
    attach.add_argument("name")
    attach.set_defaults(func=command_attach)

    run = subparsers.add_parser("run", aliases=["goal"], help="launch a detached systemd Hermes goal")
    run.add_argument("name")
    run.add_argument("goal", nargs="*", help="self-contained goal text")
    run.add_argument("--file", help="read the goal from a local file")
    run.add_argument("--budget", default=DEFAULT_BUDGET, help="wall-clock budget: 90m, 4h, 1d, or 0 for unlimited")
    run.add_argument("--trusted", action="store_true", help="process-scoped --yolo; bypass ordinary approvals")
    run.add_argument("--workdir", help="remote working directory")
    run.add_argument(
        "--reasoning",
        choices=("none", "minimal", "low", "medium", "high", "xhigh"),
        help="reasoning effort for this detached Hermes goal",
    )
    run.set_defaults(func=command_run)

    list_parser = subparsers.add_parser("list", help="list active sessions and loaded goal units")
    list_parser.set_defaults(func=command_list)

    status = subparsers.add_parser("status", help="show matching session and goal status")
    status.add_argument("name")
    status.set_defaults(func=command_status)

    logs = subparsers.add_parser("logs", help="show detached-goal systemd logs")
    logs.add_argument("name")
    logs.add_argument("--follow", "-f", action="store_true")
    logs.add_argument("--lines", type=int, default=100)
    logs.set_defaults(func=command_logs)

    stop = subparsers.add_parser("stop", help="stop a matching goal/session")
    stop.add_argument("name")
    scope = stop.add_mutually_exclusive_group()
    scope.add_argument("--goal", action="store_true", help="stop only the detached goal")
    scope.add_argument("--session", action="store_true", help="stop only the tmux session")
    stop.set_defaults(func=command_stop)

    permissions = subparsers.add_parser("permissions", help="explain and inspect approval policies")
    permissions.set_defaults(func=command_permissions)

    doctor = subparsers.add_parser("doctor", help="verify Calcifer prerequisites")
    doctor.set_defaults(func=command_doctor)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    global HOST
    parser = build_parser()
    try:
        HOST = validate_host(_HOST_RAW)
    except ValueError as exc:
        parser.exit(1, f"calcifer-agent: error: {exc}\n")
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"calcifer-agent: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
