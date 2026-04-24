#!/usr/bin/env python3
"""Daily local CI for Brayan's Hermes fork.

This script is intended to run as a Hermes cron pre-run script. It performs a
safe upstream update check for /home/brayan/.hermes/hermes-agent:

- Sync Brayan's local Hermes personalization bundle into the fork checkout
  (config template, agents, skills, plugins, scripts, cron definitions), omitting
  secrets and volatile runtime state.
- If official upstream has no commits missing from the local fork and the
  personalization snapshot did not change, emit wakeAgent=false and do nothing.
- If personalization changed, commit and push that snapshot to Brayan's fork.
- If upstream has updates, rebase Brayan's fork commit(s) onto upstream/main,
  run focused regression tests, and push the rebased main to Brayan's fork.
- If anything needs human/agent repair, emit wakeAgent=true with diagnostic
  context so the cron job wakes Darwin to investigate.

It never quotes secrets and operates only on the Hermes source checkout plus the
source-controlled Brayan personalization bundle.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path("/home/brayan/.hermes/hermes-agent")
PYTHON = REPO / "venv/bin/python"
LOG_DIR = Path("/home/brayan/.hermes/logs/hermes-upstream-ci")
LOG_DIR.mkdir(parents=True, exist_ok=True)

TEST_COMMANDS = [
    [str(PYTHON), "-m", "py_compile", "scripts/sync-brayan-personalization.py", "scripts/apply-brayan-personalization.py"],
    [
        str(PYTHON),
        "-m",
        "pytest",
        "tests/gateway/test_notes_intake_pipeline.py",
        "tests/plugins/test_notes_preprocessor_intake.py",
        "tests/cron/test_cron_script.py::TestScriptWakeGate",
        "-q",
    ],
    [
        str(PYTHON),
        "-m",
        "pytest",
        "tests/cron/test_cron_script.py",
        "tests/tools/test_cronjob_tools.py",
        "tests/hermes_cli/test_cron.py",
        "-q",
    ],
    ["/home/brayan/.local/bin/hermes", "config", "check"],
]

SENSITIVE_MARKERS = (
    "api_key",
    "token",
    "password",
    "secret",
    "authorization",
    "bearer ",
    "sk-",
    "gho_",
)

PERSONALIZATION_ALLOWED_PREFIXES = (
    "brayan-personalization/",
    "scripts/sync-brayan-personalization.py",
    "scripts/apply-brayan-personalization.py",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def redact(text: str, limit: int = 6000) -> str:
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        lower = line.lower()
        if any(marker in lower for marker in SENSITIVE_MARKERS):
            lines.append("[REDACTED SENSITIVE-LOOKING LINE]")
        else:
            lines.append(line)
    redacted = "\n".join(lines)
    if len(redacted) > limit:
        return redacted[:limit] + "\n[TRUNCATED]"
    return redacted


def run(cmd: list[str], *, check: bool = False, timeout: int = 300) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "NO_COLOR": "1"},
    )
    result = {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": redact(proc.stdout),
        "stderr": redact(proc.stderr),
    }
    if check and proc.returncode != 0:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def git(*args: str, check: bool = False, timeout: int = 300) -> dict[str, Any]:
    return run(["git", *args], check=check, timeout=timeout)


def stdout(result: dict[str, Any]) -> str:
    return str(result.get("stdout", "")).strip()


def is_ancestor(older: str, newer: str) -> bool:
    return git("merge-base", "--is-ancestor", older, newer)["returncode"] == 0


def dirty_paths() -> list[str]:
    result = git("status", "--porcelain")
    paths: list[str] = []
    for line in stdout(result).splitlines():
        if not line:
            continue
        # Porcelain v1 format: XY PATH, or XY OLD -> NEW. Use destination for renames.
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip())
    return paths


def non_personalization_dirty_paths() -> list[str]:
    return [p for p in dirty_paths() if not p.startswith(PERSONALIZATION_ALLOWED_PREFIXES)]


def sync_personalization(commands: list[dict[str, Any]]) -> bool:
    script = REPO / "scripts/sync-brayan-personalization.py"
    if not script.exists():
        fail("personalization_sync", f"Missing personalization sync script: {script}", commands=commands)
        return False
    sync = run([str(PYTHON), str(script)], timeout=300)
    commands.append(sync)
    if sync["returncode"] != 0:
        fail("personalization_sync", "Failed to sync Brayan personalization bundle; not committing/pushing.", commands=commands)
        return False
    return True


def commit_personalization_if_changed(commands: list[dict[str, Any]]) -> bool:
    changed = dirty_paths()
    if not changed:
        return False
    non_allowed = non_personalization_dirty_paths()
    if non_allowed:
        fail(
            "personalization_dirty_tree",
            "Working tree has non-personalization uncommitted changes; refusing automated commit.",
            commands=commands,
        )
        return False
    add = git("add", *PERSONALIZATION_ALLOWED_PREFIXES)
    commands.append(add)
    if add["returncode"] != 0:
        fail("personalization_add", "Failed to stage Brayan personalization snapshot.", commands=commands)
        return False
    commit = git("commit", "-m", "chore: sync Brayan Hermes personalization snapshot", timeout=120)
    commands.append(commit)
    if commit["returncode"] != 0:
        # If git says there was nothing to commit after all, treat as no change.
        if "nothing to commit" in (commit.get("stdout", "") + commit.get("stderr", "")).lower():
            return False
        fail("personalization_commit", "Failed to commit Brayan personalization snapshot.", commands=commands)
        return False
    return True


def push_origin(commands: list[dict[str, Any]], *, force_with_lease: bool = False) -> bool:
    args = ["push"]
    if force_with_lease:
        args.append("--force-with-lease")
    args.extend(["origin", "main"])
    push = git(*args, timeout=180)
    commands.append(push)
    if push["returncode"] != 0:
        fail("push", "Push to origin main failed.", commands=commands)
        return False
    if git("remote", "get-url", "brayan")["returncode"] == 0:
        brayan_args = ["push"]
        if force_with_lease:
            brayan_args.append("--force-with-lease")
        brayan_args.extend(["brayan", "main"])
        push_brayan = git(*brayan_args, timeout=180)
        commands.append(push_brayan)
        if push_brayan["returncode"] != 0:
            fail("push_brayan", "Push to origin succeeded but push to brayan alias failed.", commands=commands)
            return False
    return True


def status_snapshot() -> dict[str, Any]:
    return {
        "branch": stdout(git("branch", "--show-current")),
        "status_short": stdout(git("status", "--short", "--branch")),
        "head": stdout(git("rev-parse", "--short", "HEAD")),
        "remotes": stdout(git("remote", "-v")),
        "ahead_behind_upstream": stdout(git("rev-list", "--left-right", "--count", "upstream/main...HEAD")),
    }


def emit(payload: dict[str, Any]) -> None:
    payload.setdefault("timestamp", now())
    log_path = LOG_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    payload["log_path"] = str(log_path)
    log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


def fail(stage: str, message: str, *, commands: list[dict[str, Any]] | None = None) -> None:
    emit(
        {
            "wakeAgent": True,
            "status": "needs_agent",
            "stage": stage,
            "message": message,
            "repo": str(REPO),
            "commands": commands or [],
            "snapshot": status_snapshot(),
            "recommended_agent_action": (
                "Investigate systematically, preserve Brayan's source customizations, "
                "prefer plugin/config solutions over base-code changes where possible, "
                "resolve conflicts or failures, rerun focused tests, and push to origin/main only after verification."
            ),
        }
    )


def main() -> None:
    if not REPO.exists():
        emit({"wakeAgent": True, "status": "needs_agent", "stage": "preflight", "message": f"Repo missing: {REPO}"})
        return

    commands: list[dict[str, Any]] = []

    # Refuse to automate over in-progress Git operations.
    for marker in (REPO / ".git/rebase-merge", REPO / ".git/rebase-apply", REPO / ".git/MERGE_HEAD"):
        if marker.exists():
            fail("preflight", f"Git operation already in progress: {marker}")
            return

    branch = stdout(git("branch", "--show-current"))
    if branch != "main":
        fail("preflight", f"Expected branch main, found {branch or '[detached]'}")
        return

    non_allowed_dirty = non_personalization_dirty_paths()
    if non_allowed_dirty:
        fail("preflight", "Working tree has non-personalization uncommitted changes; refusing automated rebase/sync.")
        return

    for remote in ("origin", "upstream"):
        result = git("remote", "get-url", remote)
        if result["returncode"] != 0:
            fail("preflight", f"Missing git remote: {remote}", commands=[result])
            return

    fetch_upstream = git("fetch", "upstream", "main", "--quiet", timeout=120)
    commands.append(fetch_upstream)
    if fetch_upstream["returncode"] != 0:
        fail("fetch_upstream", "Failed to fetch official upstream/main.", commands=commands)
        return

    fetch_origin = git("fetch", "origin", "main", "--quiet", timeout=120)
    commands.append(fetch_origin)
    if fetch_origin["returncode"] != 0:
        fail("fetch_origin", "Failed to fetch fork origin/main.", commands=commands)
        return

    if is_ancestor("HEAD", "origin/main") and stdout(git("rev-parse", "HEAD")) != stdout(git("rev-parse", "origin/main")):
        ff = git("merge", "--ff-only", "origin/main")
        commands.append(ff)
        if ff["returncode"] != 0:
            fail("sync_origin", "origin/main is ahead but local main could not fast-forward.", commands=commands)
            return

    if not sync_personalization(commands):
        return
    personalization_changed = commit_personalization_if_changed(commands)
    if dirty_paths():
        return

    if is_ancestor("upstream/main", "HEAD"):
        if personalization_changed:
            for test_cmd in TEST_COMMANDS:
                test = run(test_cmd, timeout=600)
                commands.append(test)
                if test["returncode"] != 0:
                    fail("tests", "Personalization sync verification failed; not pushing main.", commands=commands)
                    return
            if not push_origin(commands):
                return
        emit(
            {
                "wakeAgent": False,
                "status": "personalization_synced" if personalization_changed else "up_to_date",
                "message": (
                    "Synced and pushed Brayan's Hermes personalization snapshot."
                    if personalization_changed
                    else "Local/fork main already contains upstream/main and personalization snapshot is unchanged; no agent needed."
                ),
                "repo": str(REPO),
                "snapshot": status_snapshot(),
                "commands": commands,
            }
        )
        return

    before = stdout(git("rev-parse", "--short", "HEAD"))
    upstream = stdout(git("rev-parse", "--short", "upstream/main"))

    rebase = git("rebase", "upstream/main", timeout=300)
    commands.append(rebase)
    if rebase["returncode"] != 0:
        fail(
            "rebase",
            f"Rebase onto upstream/main failed. Repo may be mid-rebase; resolve conflicts before continuing. Before={before}, upstream={upstream}.",
            commands=commands,
        )
        return

    for test_cmd in TEST_COMMANDS:
        test = run(test_cmd, timeout=600)
        commands.append(test)
        if test["returncode"] != 0:
            fail("tests", "Post-rebase verification failed; not pushing rebased main.", commands=commands)
            return

    if not push_origin(commands, force_with_lease=True):
        return

    emit(
        {
            "wakeAgent": False,
            "status": "updated",
            "message": "Rebased Brayan's fork onto upstream/main, tests passed, and pushed fork main. No agent needed.",
            "repo": str(REPO),
            "before": before,
            "after": stdout(git("rev-parse", "--short", "HEAD")),
            "upstream": upstream,
            "snapshot": status_snapshot(),
            "commands": commands,
        }
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.TimeoutExpired as exc:
        emit(
            {
                "wakeAgent": True,
                "status": "needs_agent",
                "stage": "timeout",
                "message": f"Command timed out: {exc.cmd}",
                "repo": str(REPO),
                "snapshot": status_snapshot() if REPO.exists() else {},
            }
        )
    except Exception as exc:
        emit(
            {
                "wakeAgent": True,
                "status": "needs_agent",
                "stage": "unexpected_exception",
                "message": redact(repr(exc)),
                "repo": str(REPO),
                "snapshot": status_snapshot() if REPO.exists() else {},
            }
        )
