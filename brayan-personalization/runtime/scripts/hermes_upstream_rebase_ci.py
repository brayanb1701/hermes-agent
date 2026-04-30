#!/usr/bin/env python3
"""Daily local CI for Brayan's Hermes fork.

This script is intended to run as a Hermes cron pre-run script. It performs a
safe upstream update check for /home/brayan/.hermes/hermes-agent:

- Fetch official upstream updates and the fork's personalization branch.
- Fast-forward the local personalization branch from origin if needed.
- Sync Brayan's current local Hermes personalization bundle into the fork checkout
  (config template, agents, skills, plugins, scripts, cron definitions), omitting
  secrets and volatile runtime state.
- If the personalization snapshot changed, commit it on the personalization branch.
- Rebase Brayan's personalization branch onto upstream/main so the branch becomes:
  latest official Hermes + Brayan source changes + latest local personalization snapshot.
- Run focused regression tests and push only the target personalization branch.
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
TARGET_BRANCH = "brayan/personal-hermes-customizations"
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
        "-o",
        "addopts=",
    ],
    [
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
        env={**os.environ, "NO_COLOR": "1", "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"},
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


def configure_git_automation(commands: list[dict[str, Any]]) -> None:
    """Enable Git helpers that make repeated rebases less manual.

    rerere records conflict resolutions. If upstream produces the same conflict
    again, Git can reuse the prior resolution instead of waking the agent for
    the same manual edit. autoupdate stages reused resolutions so the script can
    continue the rebase non-interactively when all conflicts were resolved.
    """
    for key, value in (("rerere.enabled", "true"), ("rerere.autoupdate", "true")):
        result = git("config", key, value)
        commands.append(result)


def unmerged_paths() -> list[str]:
    result = git("diff", "--name-only", "--diff-filter=U")
    return [line.strip() for line in stdout(result).splitlines() if line.strip()]


def rebase_in_progress() -> bool:
    return any((REPO / marker).exists() for marker in (".git/rebase-merge", ".git/rebase-apply"))


def try_continue_resolved_rebase(commands: list[dict[str, Any]]) -> bool:
    """Continue a rebase if rerere/autoupdate resolved every conflict.

    Returns True only when the rebase completed successfully. If conflicts remain
    or continue fails, callers should wake the agent with diagnostics.
    """
    if not rebase_in_progress() or unmerged_paths():
        return False
    status = git("status", "--porcelain")
    commands.append(status)
    cont = git("rebase", "--continue", timeout=300)
    commands.append(cont)
    return cont["returncode"] == 0


def stdout(result: dict[str, Any]) -> str:
    return str(result.get("stdout", "")).strip()


def is_ancestor(older: str, newer: str) -> bool:
    return git("merge-base", "--is-ancestor", older, newer)["returncode"] == 0


def dirty_paths() -> list[str]:
    # Use raw subprocess output here, not git()/run(), because run() redacts and
    # truncates command output for logs. Large personalization snapshots can make
    # `git status --porcelain` exceed the log limit; parsing the truncated text
    # produces bogus paths like "UNCATED]" and falsely trips the dirty-tree gate.
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "NO_COLOR": "1", "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"},
    )
    paths: list[str] = []
    for line in proc.stdout.splitlines():
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
    args.extend(["origin", f"HEAD:{TARGET_BRANCH}"])
    push = git(*args, timeout=180)
    commands.append(push)
    if push["returncode"] != 0:
        fail("push", f"Push to origin/{TARGET_BRANCH} failed.", commands=commands)
        return False
    if git("remote", "get-url", "brayan")["returncode"] == 0:
        brayan_args = ["push"]
        if force_with_lease:
            brayan_args.append("--force-with-lease")
        brayan_args.extend(["brayan", f"HEAD:{TARGET_BRANCH}"])
        push_brayan = git(*brayan_args, timeout=180)
        commands.append(push_brayan)
        if push_brayan["returncode"] != 0:
            fail("push_brayan", f"Push to origin/{TARGET_BRANCH} succeeded but push to brayan alias failed.", commands=commands)
            return False
    return True


def status_snapshot() -> dict[str, Any]:
    return {
        "branch": stdout(git("branch", "--show-current")),
        "status_short": stdout(git("status", "--short", "--branch")),
        "head": stdout(git("rev-parse", "--short", "HEAD")),
        "remotes": stdout(git("remote", "-v")),
        "ahead_behind_upstream": stdout(git("rev-list", "--left-right", "--count", "upstream/main...HEAD")),
        "unmerged_paths": unmerged_paths(),
        "rebase_in_progress": rebase_in_progress(),
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
                f"resolve conflicts or failures, rerun focused tests, and push only to origin/{TARGET_BRANCH} after verification."
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
    if branch != TARGET_BRANCH:
        fail("preflight", f"Expected branch {TARGET_BRANCH}, found {branch or '[detached]'}")
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

    configure_git_automation(commands)

    fetch_upstream = git("fetch", "upstream", "main", "--quiet", timeout=120)
    commands.append(fetch_upstream)
    if fetch_upstream["returncode"] != 0:
        fail("fetch_upstream", "Failed to fetch official upstream/main.", commands=commands)
        return

    fetch_origin = git("fetch", "origin", TARGET_BRANCH, "--quiet", timeout=120)
    commands.append(fetch_origin)
    if fetch_origin["returncode"] != 0:
        fail("fetch_origin", f"Failed to fetch fork origin/{TARGET_BRANCH}.", commands=commands)
        return

    remote_target = f"origin/{TARGET_BRANCH}"
    if is_ancestor("HEAD", remote_target) and stdout(git("rev-parse", "HEAD")) != stdout(git("rev-parse", remote_target)):
        ff = git("merge", "--ff-only", remote_target)
        commands.append(ff)
        if ff["returncode"] != 0:
            fail("sync_origin", f"origin/{TARGET_BRANCH} is ahead but local branch could not fast-forward.", commands=commands)
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
                    fail("tests", f"Personalization sync verification failed; not pushing {TARGET_BRANCH}.", commands=commands)
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
                    else f"Local/fork {TARGET_BRANCH} already contains upstream/main and personalization snapshot is unchanged; no agent needed."
                ),
                "repo": str(REPO),
                "snapshot": status_snapshot(),
                "commands": commands,
            }
        )
        return

    before = stdout(git("rev-parse", "--short", "HEAD"))
    upstream = stdout(git("rev-parse", "--short", "upstream/main"))

    rebase = git("rebase", "upstream/main", timeout=600)
    commands.append(rebase)
    if rebase["returncode"] != 0:
        if try_continue_resolved_rebase(commands):
            commands.append({"cmd": ["git", "rebase", "--continue"], "returncode": 0, "stdout": "Rebase continued automatically after rerere/autoupdate resolved conflicts.", "stderr": ""})
        else:
            fail(
                "rebase",
                f"Rebase onto upstream/main failed. Repo may be mid-rebase; resolve conflicts before continuing. Before={before}, upstream={upstream}. Unmerged paths: {', '.join(unmerged_paths()) or 'none reported'}.",
                commands=commands,
            )
            return

    for test_cmd in TEST_COMMANDS:
        test = run(test_cmd, timeout=600)
        commands.append(test)
        if test["returncode"] != 0:
            fail("tests", f"Post-rebase verification failed; not pushing rebased {TARGET_BRANCH}.", commands=commands)
            return

    if not push_origin(commands, force_with_lease=True):
        return

    emit(
        {
            "wakeAgent": False,
            "status": "updated",
            "message": f"Rebased Brayan's {TARGET_BRANCH} onto upstream/main, tests passed, and pushed the personalization branch. No agent needed.",
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
