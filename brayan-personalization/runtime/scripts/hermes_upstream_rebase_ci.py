#!/usr/bin/env python3
"""Daily local CI for Brayan's Hermes fork.

This script is intended to run as a Hermes cron pre-run script. It performs a
safe upstream update check for Brayan's Hermes personalization branch while
protecting the live gateway checkout during rebase/testing:

- The live executable checkout is /home/brayan/.hermes/hermes-agent.
- Rebases/tests run in an isolated detached git worktree under
  /home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci.
- The worktree starts from the newer compatible base between the live target
  branch and origin/brayan/personal-hermes-customizations.
- Brayan's current runtime personalization bundle is synced into that worktree,
  committed if changed, rebased onto upstream/main, tested, and pushed only to
  the personalization branch.
- If a rebase conflict or test failure happens, the broken state stays in the
  isolated worktree. The live checkout used by the gateway is not left with
  conflict markers or mixed source files.
- After a verified candidate is pushed, a detached systemd transient unit runs
  ``hermes update --branch brayan/personal-hermes-customizations``. That
  supported updater path activates the verified commit, refreshes dependencies
  and config, and restarts the gateway without killing this cron run early.

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

LIVE_REPO = Path("/home/brayan/.hermes/hermes-agent")
WORKTREE = Path("/home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci")
REPO = WORKTREE
TARGET_BRANCH = "brayan/personal-hermes-customizations"
PYTHON = LIVE_REPO / "venv/bin/python"
HERMES_CLI = Path("/home/brayan/.local/bin/hermes")
RUNTIME_SCRIPT = Path("/home/brayan/.hermes/scripts/hermes_upstream_rebase_ci.py")
LOG_DIR = Path("/home/brayan/.hermes/logs/hermes-upstream-ci")
LOG_DIR.mkdir(parents=True, exist_ok=True)

TEST_COMMANDS = [
    [
        str(PYTHON),
        "-m",
        "py_compile",
        str(RUNTIME_SCRIPT),
        "scripts/sync-brayan-personalization.py",
        "scripts/apply-brayan-personalization.py",
        "gateway/run.py",
        "agent/agent_init.py",
        "agent/context_compressor.py",
    ],
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


def live_activation_required(candidate_head: str, live_head: str) -> bool:
    """Return whether the verified candidate still needs live activation."""
    return bool(candidate_head and live_head and candidate_head != live_head)


def build_live_activation_command(candidate_head: str) -> list[str]:
    """Build a detached, branch-safe live updater command.

    The transient unit runs outside the gateway service cgroup, so the updater
    survives the gateway restart it performs after dependency/config refresh.
    """
    unit = f"hermes-personalization-activate-{candidate_head[:12]}"
    return [
        "systemd-run",
        "--user",
        "--collect",
        "--on-active=5s",
        f"--unit={unit}",
        "--property=TimeoutStartSec=1800",
        str(HERMES_CLI),
        "update",
        "--branch",
        TARGET_BRANCH,
        "--yes",
        "--no-backup",
    ]


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


def run(
    cmd: list[str],
    *,
    check: bool = False,
    timeout: int = 300,
    cwd: Path | None = None,
) -> dict[str, Any]:
    run_cwd = cwd or REPO
    proc = subprocess.run(
        cmd,
        cwd=run_cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "NO_COLOR": "1", "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"},
    )
    result = {
        "cmd": cmd,
        "cwd": str(run_cwd),
        "returncode": proc.returncode,
        "stdout": redact(proc.stdout),
        "stderr": redact(proc.stderr),
    }
    if check and proc.returncode != 0:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def git(*args: str, check: bool = False, timeout: int = 300, cwd: Path | None = None) -> dict[str, Any]:
    return run(["git", *args], check=check, timeout=timeout, cwd=cwd)


def stdout(result: dict[str, Any]) -> str:
    return str(result.get("stdout", "")).strip()


def is_ancestor(older: str, newer: str, *, cwd: Path | None = None) -> bool:
    return git("merge-base", "--is-ancestor", older, newer, cwd=cwd)["returncode"] == 0


def git_path(repo: Path, path_name: str) -> Path:
    result = git("rev-parse", "--git-path", path_name, cwd=repo)
    if result["returncode"] != 0:
        return repo / ".git" / path_name
    raw = stdout(result)
    if not raw:
        return repo / ".git" / path_name
    path = Path(raw)
    return path if path.is_absolute() else repo / path


def git_operation_in_progress(repo: Path) -> bool:
    return any(git_path(repo, marker).exists() for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD"))


def rebase_in_progress(repo: Path | None = None) -> bool:
    check_repo = repo or REPO
    return any(git_path(check_repo, marker).exists() for marker in ("rebase-merge", "rebase-apply"))


def unmerged_paths(repo: Path | None = None) -> list[str]:
    check_repo = repo or REPO
    result = git("diff", "--name-only", "--diff-filter=U", cwd=check_repo)
    return [line.strip() for line in stdout(result).splitlines() if line.strip()]


def dirty_paths(repo: Path | None = None) -> list[str]:
    check_repo = repo or REPO
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=check_repo,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "NO_COLOR": "1", "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"},
    )
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip())
    return paths


def non_personalization_dirty_paths(repo: Path | None = None) -> list[str]:
    return [p for p in dirty_paths(repo) if not p.startswith(PERSONALIZATION_ALLOWED_PREFIXES)]


def configure_git_automation(commands: list[dict[str, Any]]) -> None:
    """Enable Git helpers that make repeated rebases less manual."""
    for key, value in (("rerere.enabled", "true"), ("rerere.autoupdate", "true")):
        result = git("config", key, value, cwd=LIVE_REPO)
        commands.append(result)


def ensure_clean_worktree_slot(commands: list[dict[str, Any]]) -> bool:
    WORKTREE.parent.mkdir(parents=True, exist_ok=True)
    prune = git("worktree", "prune", cwd=LIVE_REPO)
    commands.append(prune)

    if not WORKTREE.exists():
        return True

    if not (WORKTREE / ".git").exists():
        fail(
            "worktree_preflight",
            f"Worktree path exists but is not a git worktree: {WORKTREE}. Move it aside before automated CI continues.",
            commands=commands,
            repo=LIVE_REPO,
        )
        return False

    if git_operation_in_progress(WORKTREE) or dirty_paths(WORKTREE):
        fail(
            "worktree_dirty",
            "Previous CI worktree has an in-progress git operation or uncommitted changes; leaving it intact for inspection.",
            commands=commands,
            repo=WORKTREE,
        )
        return False

    remove = git("worktree", "remove", "--force", str(WORKTREE), cwd=LIVE_REPO, timeout=120)
    commands.append(remove)
    if remove["returncode"] != 0:
        fail("worktree_remove", "Failed to remove clean stale CI worktree.", commands=commands, repo=WORKTREE)
        return False
    return True


def remote_preserves_telegram_pending_updates(remote_target: str, commands: list[dict[str, Any]]) -> bool:
    """Known-safe equivalence check for the Telegram polling preservation fix.

    Upstream refactors moved the Telegram adapter from gateway/platforms/telegram.py
    into plugins/platforms/telegram/adapter.py. That makes git cherry report the
    old live commit as non-patch-equivalent even when origin already carries the
    same behavioral fix in the new file layout. Only treat origin as equivalent
    when both the behavior and its regression test are present on the remote.
    """
    subject = "fix: preserve Telegram updates during polling startup"
    same_subject = git(
        "log",
        "--format=%H",
        "--max-count=1",
        "--fixed-strings",
        f"--grep={subject}",
        remote_target,
        cwd=LIVE_REPO,
    )
    commands.append(same_subject)
    if same_subject["returncode"] != 0 or not stdout(same_subject):
        return False

    grep_code = git(
        "grep",
        "-n",
        "drop_pending_updates=False",
        remote_target,
        "--",
        "gateway/platforms/telegram.py",
        "plugins/platforms/telegram/adapter.py",
        cwd=LIVE_REPO,
    )
    commands.append(grep_code)
    if grep_code["returncode"] != 0 or "drop_pending_updates=False" not in str(grep_code.get("stdout", "")):
        return False

    grep_test = git(
        "grep",
        "-n",
        "test_polling_connect_preserves_pending_updates",
        remote_target,
        "--",
        "tests/gateway/test_telegram_conflict.py",
        "tests/gateway/test_telegram_platform.py",
        cwd=LIVE_REPO,
    )
    commands.append(grep_test)
    return grep_test["returncode"] == 0 and "test_polling_connect_preserves_pending_updates" in str(grep_test.get("stdout", ""))


def remote_preserves_notes_intake_isolation(remote_target: str, commands: list[dict[str, Any]]) -> bool:
    """Known-safe equivalence check for the Anything Inbox / cron wake-gate commit.

    Repeated rebases rewrite the original notes-intake feature commit onto newer
    upstream gateway/cron code, so the old live commit can appear as a '+' in
    ``git cherry`` even when origin already carries the same behavior. Treat it
    as equivalent only when the rebased origin branch has the same subject plus
    the source and regression-test anchors that protect the behavior.
    """
    subject = "feat: add notes intake isolation and cron wake gate"
    same_subject = git(
        "log",
        "--format=%H",
        "--max-count=1",
        "--fixed-strings",
        f"--grep={subject}",
        remote_target,
        cwd=LIVE_REPO,
    )
    commands.append(same_subject)
    if same_subject["returncode"] != 0 or not stdout(same_subject):
        return False

    required_greps = [
        (
            "notes-intake helper",
            "enrich_anything_inbox_image",
            ("gateway/notes_intake.py",),
        ),
        (
            "Anything Inbox source routing",
            "is_anything_inbox_source",
            ("gateway/run.py",),
        ),
        (
            "wake-gate parser",
            "ready_count",
            ("cron/scheduler.py",),
        ),
        (
            "vision MIME regression",
            "test_make_vision_messages_sniffs_mime_type_from_image_bytes",
            ("tests/gateway/test_notes_intake_pipeline.py",),
        ),
        (
            "wake-gate regression",
            "test_ready_count_zero_skips_agent_for_pretty_json",
            ("tests/cron/test_cron_script.py",),
        ),
    ]
    for _label, pattern, paths in required_greps:
        grep = git("grep", "-n", pattern, remote_target, "--", *paths, cwd=LIVE_REPO)
        commands.append(grep)
        if grep["returncode"] != 0 or pattern not in str(grep.get("stdout", "")):
            return False
    return True


def known_live_plus_commits_equivalent_on_origin(
    live_cherry_lines: list[str], remote_target: str, commands: list[dict[str, Any]]
) -> bool:
    """Return True when every live-only '+' commit is a known-safe origin equivalent."""
    plus_subjects: list[str] = []
    for line in live_cherry_lines:
        if not line.startswith("+ "):
            continue
        parts = line.split(" ", 2)
        if len(parts) < 3:
            return False
        plus_subjects.append(parts[2])

    if not plus_subjects:
        return False

    for subject in plus_subjects:
        if subject == "fix: preserve Telegram updates during polling startup":
            if not remote_preserves_telegram_pending_updates(remote_target, commands):
                return False
            continue
        if subject == "feat: add notes intake isolation and cron wake gate":
            if not remote_preserves_notes_intake_isolation(remote_target, commands):
                return False
            continue
        return False
    return True


def choose_base_ref(commands: list[dict[str, Any]]) -> str | None:
    branch = stdout(git("branch", "--show-current", cwd=LIVE_REPO))

    live_dirty = dirty_paths(LIVE_REPO)
    if live_dirty:
        fail(
            "preflight",
            "Live checkout has uncommitted changes; refusing automated update. The CI now uses an isolated worktree, but live source changes still need explicit review before they are used as the update base.",
            commands=commands,
            repo=LIVE_REPO,
        )
        return None

    fetch_upstream = git("fetch", "upstream", "main", "--quiet", cwd=LIVE_REPO, timeout=120)
    commands.append(fetch_upstream)
    if fetch_upstream["returncode"] != 0:
        fail("fetch_upstream", "Failed to fetch official upstream/main.", commands=commands, repo=LIVE_REPO)
        return None

    fetch_origin = git("fetch", "origin", TARGET_BRANCH, "--quiet", cwd=LIVE_REPO, timeout=120)
    commands.append(fetch_origin)
    if fetch_origin["returncode"] != 0:
        fail("fetch_origin", f"Failed to fetch fork origin/{TARGET_BRANCH}.", commands=commands, repo=LIVE_REPO)
        return None

    remote_target = f"origin/{TARGET_BRANCH}"
    remote_head = stdout(git("rev-parse", remote_target, cwd=LIVE_REPO))
    if not remote_head:
        fail("preflight", f"Could not resolve {remote_target}.", commands=commands, repo=LIVE_REPO)
        return None

    # Raw ``hermes update`` historically defaults to main. If that moved the
    # live checkout away from the personalization branch, recover from the
    # remote integration branch and let the post-verification activation step
    # switch the live checkout back safely.
    if branch != TARGET_BRANCH:
        commands.append(
            {
                "cmd": ["git", "branch", "--show-current"],
                "cwd": str(LIVE_REPO),
                "returncode": 0,
                "stdout": f"Live checkout is on {branch or '[detached]'}; using {remote_target} as recovery base.",
                "stderr": "",
            }
        )
        return remote_head

    live_head = stdout(git("rev-parse", "HEAD", cwd=LIVE_REPO))
    if not live_head:
        fail("preflight", "Could not resolve live HEAD.", commands=commands, repo=LIVE_REPO)
        return None

    if is_ancestor(live_head, remote_target, cwd=LIVE_REPO):
        return remote_head
    if is_ancestor(remote_target, live_head, cwd=LIVE_REPO):
        return live_head

    # A successful prior isolated rebase/push can leave the live checkout's
    # branch ref on the pre-rebase commits while origin contains patch-equivalent
    # rebased versions of the same local changes. In that case, choosing origin
    # preserves the live changes without replaying stale duplicate commits.
    live_cherry_cmd = ["git", "cherry", "-v", remote_target, "HEAD"]
    live_cherry_proc = subprocess.run(
        live_cherry_cmd,
        cwd=LIVE_REPO,
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "NO_COLOR": "1", "GIT_EDITOR": "true", "GIT_SEQUENCE_EDITOR": "true"},
    )
    commands.append(
        {
            "cmd": live_cherry_cmd,
            "cwd": str(LIVE_REPO),
            "returncode": live_cherry_proc.returncode,
            "stdout": redact(live_cherry_proc.stdout),
            "stderr": redact(live_cherry_proc.stderr),
        }
    )
    if live_cherry_proc.returncode == 0:
        live_cherry_lines = [line for line in live_cherry_proc.stdout.splitlines() if line.strip()]
        if live_cherry_lines and all(line.startswith("- ") for line in live_cherry_lines):
            return remote_head
        if live_cherry_lines and known_live_plus_commits_equivalent_on_origin(live_cherry_lines, remote_target, commands):
            return remote_head

    fail(
        "preflight",
        f"Live {TARGET_BRANCH} and origin/{TARGET_BRANCH} have diverged. Refusing to choose a base automatically.",
        commands=commands,
        repo=LIVE_REPO,
    )
    return None


def prepare_worktree(base_ref: str, commands: list[dict[str, Any]]) -> bool:
    if not ensure_clean_worktree_slot(commands):
        return False
    add = git("worktree", "add", "--detach", str(WORKTREE), base_ref, cwd=LIVE_REPO, timeout=180)
    commands.append(add)
    if add["returncode"] != 0:
        fail("worktree_add", f"Failed to create isolated CI worktree at {WORKTREE}.", commands=commands, repo=LIVE_REPO)
        return False
    return True


def sync_personalization(commands: list[dict[str, Any]]) -> bool:
    script = REPO / "scripts/sync-brayan-personalization.py"
    if not script.exists():
        fail("personalization_sync", f"Missing personalization sync script: {script}", commands=commands, repo=REPO)
        return False
    sync = run([str(PYTHON), str(script)], timeout=300, cwd=REPO)
    commands.append(sync)
    if sync["returncode"] != 0:
        fail("personalization_sync", "Failed to sync Brayan personalization bundle; not committing/pushing.", commands=commands, repo=REPO)
        return False
    return True


def commit_personalization_if_changed(commands: list[dict[str, Any]]) -> bool:
    changed = dirty_paths(REPO)
    if not changed:
        return False
    non_allowed = non_personalization_dirty_paths(REPO)
    if non_allowed:
        fail(
            "personalization_dirty_tree",
            "Working tree has non-personalization uncommitted changes; refusing automated commit.",
            commands=commands,
            repo=REPO,
        )
        return False
    add = git("add", *PERSONALIZATION_ALLOWED_PREFIXES, cwd=REPO)
    commands.append(add)
    if add["returncode"] != 0:
        fail("personalization_add", "Failed to stage Brayan personalization snapshot.", commands=commands, repo=REPO)
        return False
    commit = git("commit", "-m", "chore: sync Brayan Hermes personalization snapshot", cwd=REPO, timeout=120)
    commands.append(commit)
    if commit["returncode"] != 0:
        combined = (commit.get("stdout", "") + commit.get("stderr", "")).lower()
        if "nothing to commit" in combined:
            return False
        fail("personalization_commit", "Failed to commit Brayan personalization snapshot.", commands=commands, repo=REPO)
        return False
    return True


def push_origin(commands: list[dict[str, Any]], *, force_with_lease: bool = False) -> bool:
    args = ["push"]
    observed_origin = stdout(git("rev-parse", f"origin/{TARGET_BRANCH}", cwd=REPO))
    if force_with_lease:
        if not observed_origin:
            fail("push", f"Could not resolve origin/{TARGET_BRANCH} for exact force-with-lease.", commands=commands, repo=REPO)
            return False
        args.append(f"--force-with-lease=refs/heads/{TARGET_BRANCH}:{observed_origin}")
    args.extend(["origin", f"HEAD:{TARGET_BRANCH}"])
    push = git(*args, cwd=REPO, timeout=180)
    commands.append(push)
    if push["returncode"] != 0:
        fail("push", f"Push to origin/{TARGET_BRANCH} failed.", commands=commands, repo=REPO)
        return False

    origin_url = stdout(git("remote", "get-url", "origin", cwd=REPO))
    brayan_url_result = git("remote", "get-url", "brayan", cwd=REPO)
    if brayan_url_result["returncode"] == 0:
        brayan_url = stdout(brayan_url_result)
        if brayan_url and brayan_url != origin_url:
            fetch_brayan = git("fetch", "brayan", TARGET_BRANCH, "--quiet", cwd=REPO, timeout=120)
            commands.append(fetch_brayan)
            if fetch_brayan["returncode"] != 0:
                fail("fetch_brayan", f"origin push succeeded but fetch from brayan/{TARGET_BRANCH} failed.", commands=commands, repo=REPO)
                return False
            brayan_args = ["push"]
            if force_with_lease:
                observed_brayan = stdout(git("rev-parse", f"brayan/{TARGET_BRANCH}", cwd=REPO))
                if not observed_brayan:
                    fail("push_brayan", f"Could not resolve brayan/{TARGET_BRANCH} for exact force-with-lease.", commands=commands, repo=REPO)
                    return False
                brayan_args.append(f"--force-with-lease=refs/heads/{TARGET_BRANCH}:{observed_brayan}")
            brayan_args.extend(["brayan", f"HEAD:{TARGET_BRANCH}"])
            push_brayan = git(*brayan_args, cwd=REPO, timeout=180)
            commands.append(push_brayan)
            if push_brayan["returncode"] != 0:
                fail("push_brayan", f"Push to brayan/{TARGET_BRANCH} failed after origin push succeeded.", commands=commands, repo=REPO)
                return False
    return True


def schedule_live_activation(commands: list[dict[str, Any]], candidate_head: str) -> bool | None:
    """Schedule activation of a verified/pushed candidate outside the gateway.

    Returns ``True`` when a transient updater was scheduled, ``False`` when the
    live checkout already matches, and ``None`` after emitting a failure.
    """
    live_head = stdout(git("rev-parse", "HEAD", cwd=LIVE_REPO))
    if not live_head:
        fail("activation_preflight", "Could not resolve live HEAD before activation.", commands=commands, repo=LIVE_REPO)
        return None
    if not live_activation_required(candidate_head, live_head):
        return False

    command = build_live_activation_command(candidate_head)
    scheduled = run(command, timeout=120, cwd=LIVE_REPO)
    commands.append(scheduled)
    if scheduled["returncode"] != 0:
        fail(
            "activation_schedule",
            "Verified candidate was pushed, but the detached live updater could not be scheduled.",
            commands=commands,
            repo=LIVE_REPO,
        )
        return None
    return True


def status_snapshot(repo: Path | None = None) -> dict[str, Any]:
    snap_repo = repo or (REPO if REPO.exists() else LIVE_REPO)
    data: dict[str, Any] = {"repo": str(snap_repo), "repo_exists": snap_repo.exists()}
    if not snap_repo.exists():
        return data
    for key, args in {
        "branch": ["branch", "--show-current"],
        "status_short": ["status", "--short", "--branch"],
        "head": ["rev-parse", "--short", "HEAD"],
        "remotes": ["remote", "-v"],
        "ahead_behind_upstream": ["rev-list", "--left-right", "--count", "upstream/main...HEAD"],
    }.items():
        result = git(*args, cwd=snap_repo)
        data[key] = stdout(result) if result["returncode"] == 0 else redact(result.get("stderr", ""))
    data["unmerged_paths"] = unmerged_paths(snap_repo)
    data["rebase_in_progress"] = rebase_in_progress(snap_repo)
    if snap_repo != LIVE_REPO and LIVE_REPO.exists():
        live_head = git("rev-parse", "--short", "HEAD", cwd=LIVE_REPO)
        live_status = git("status", "--short", "--branch", cwd=LIVE_REPO)
        data["live_checkout"] = {
            "repo": str(LIVE_REPO),
            "head": stdout(live_head) if live_head["returncode"] == 0 else "",
            "status_short": stdout(live_status) if live_status["returncode"] == 0 else "",
            "git_operation_in_progress": git_operation_in_progress(LIVE_REPO),
        }
    return data


def emit(payload: dict[str, Any]) -> None:
    payload.setdefault("timestamp", now())
    log_path = LOG_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    payload["log_path"] = str(log_path)
    log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


def fail(stage: str, message: str, *, commands: list[dict[str, Any]] | None = None, repo: Path | None = None) -> None:
    emit(
        {
            "wakeAgent": True,
            "status": "needs_agent",
            "stage": stage,
            "message": message,
            "repo": str(repo or (REPO if REPO.exists() else LIVE_REPO)),
            "live_repo": str(LIVE_REPO),
            "worktree": str(WORKTREE),
            "commands": commands or [],
            "snapshot": status_snapshot(repo),
            "recommended_agent_action": (
                "Investigate systematically. If the failure is in the isolated worktree, "
                "resolve conflicts there or remove the worktree only after confirming it is clean. "
                f"Preserve Brayan's source customizations and push only origin/{TARGET_BRANCH} after verification."
            ),
        }
    )


def try_continue_resolved_rebase(commands: list[dict[str, Any]]) -> bool:
    """Continue a rebase if rerere/autoupdate resolved every conflict."""
    if not rebase_in_progress(REPO) or unmerged_paths(REPO):
        return False
    status = git("status", "--porcelain", cwd=REPO)
    commands.append(status)
    cont = git("rebase", "--continue", cwd=REPO, timeout=300)
    commands.append(cont)
    return cont["returncode"] == 0


def run_verification(commands: list[dict[str, Any]], *, failure_stage: str) -> bool:
    for test_cmd in TEST_COMMANDS:
        test = run(test_cmd, timeout=600, cwd=REPO)
        commands.append(test)
        if test["returncode"] != 0:
            fail(failure_stage, f"Verification failed; not pushing {TARGET_BRANCH}.", commands=commands, repo=REPO)
            return False
    return True


def main() -> None:
    if not LIVE_REPO.exists():
        emit({"wakeAgent": True, "status": "needs_agent", "stage": "preflight", "message": f"Live repo missing: {LIVE_REPO}"})
        return

    commands: list[dict[str, Any]] = []

    if git_operation_in_progress(LIVE_REPO):
        fail("preflight", "Live checkout already has an in-progress git operation; refusing to automate over it.", repo=LIVE_REPO)
        return

    for remote in ("origin", "upstream"):
        result = git("remote", "get-url", remote, cwd=LIVE_REPO)
        if result["returncode"] != 0:
            fail("preflight", f"Missing git remote on live checkout: {remote}", commands=[result], repo=LIVE_REPO)
            return

    configure_git_automation(commands)
    base_ref = choose_base_ref(commands)
    if not base_ref:
        return
    if not prepare_worktree(base_ref, commands):
        return

    if not sync_personalization(commands):
        return
    personalization_changed = commit_personalization_if_changed(commands)
    if dirty_paths(REPO):
        fail("personalization_dirty_tree", "Personalization sync left unstaged/uncommitted changes; refusing to continue.", commands=commands, repo=REPO)
        return

    if is_ancestor("upstream/main", "HEAD", cwd=REPO):
        candidate_head = stdout(git("rev-parse", "HEAD", cwd=REPO))
        observed_origin = stdout(git("rev-parse", f"origin/{TARGET_BRANCH}", cwd=REPO))
        live_head = stdout(git("rev-parse", "HEAD", cwd=LIVE_REPO))
        remote_needs_push = bool(candidate_head and candidate_head != observed_origin)
        activation_needed = live_activation_required(candidate_head, live_head)

        if personalization_changed or remote_needs_push or activation_needed:
            if not run_verification(commands, failure_stage="tests"):
                return
        if personalization_changed or remote_needs_push:
            if not push_origin(commands, force_with_lease=False):
                return

        activation_scheduled = schedule_live_activation(commands, candidate_head)
        if activation_scheduled is None:
            return
        status = (
            "personalization_synced"
            if personalization_changed
            else "updated"
            if remote_needs_push or activation_scheduled
            else "up_to_date"
        )
        message = (
            f"Verified and pushed {TARGET_BRANCH}; detached live activation scheduled."
            if activation_scheduled
            else f"origin/{TARGET_BRANCH}, upstream/main, and the live checkout are synchronized."
        )
        emit(
            {
                "wakeAgent": False,
                "status": status,
                "message": message,
                "activation_scheduled": activation_scheduled,
                "candidate_head": candidate_head,
                "repo": str(REPO),
                "live_repo": str(LIVE_REPO),
                "snapshot": status_snapshot(REPO),
                "commands": commands,
            }
        )
        return

    before = stdout(git("rev-parse", "--short", "HEAD", cwd=REPO))
    upstream = stdout(git("rev-parse", "--short", "upstream/main", cwd=REPO))

    rebase = git("rebase", "upstream/main", cwd=REPO, timeout=600)
    commands.append(rebase)
    rebase_needed_force_push = False
    if rebase["returncode"] != 0:
        if try_continue_resolved_rebase(commands):
            commands.append({"cmd": ["git", "rebase", "--continue"], "cwd": str(REPO), "returncode": 0, "stdout": "Rebase continued automatically after rerere/autoupdate resolved conflicts.", "stderr": ""})
            rebase_needed_force_push = True
        else:
            fail(
                "rebase",
                f"Rebase onto upstream/main failed in isolated worktree. Live gateway checkout was not mutated. Before={before}, upstream={upstream}. Unmerged paths: {', '.join(unmerged_paths(REPO)) or 'none reported'}.",
                commands=commands,
                repo=REPO,
            )
            return
    else:
        rebase_needed_force_push = True

    if not run_verification(commands, failure_stage="tests"):
        return

    if not push_origin(commands, force_with_lease=rebase_needed_force_push):
        return

    candidate_head = stdout(git("rev-parse", "HEAD", cwd=REPO))
    activation_scheduled = schedule_live_activation(commands, candidate_head)
    if activation_scheduled is None:
        return

    emit(
        {
            "wakeAgent": False,
            "status": "updated",
            "message": (
                f"Rebased and pushed Brayan's {TARGET_BRANCH}; detached live activation scheduled."
                if activation_scheduled
                else f"Rebased and pushed Brayan's {TARGET_BRANCH}; live checkout already matched."
            ),
            "activation_scheduled": activation_scheduled,
            "candidate_head": candidate_head,
            "repo": str(REPO),
            "live_repo": str(LIVE_REPO),
            "before": before,
            "after": stdout(git("rev-parse", "--short", "HEAD", cwd=REPO)),
            "upstream": upstream,
            "snapshot": status_snapshot(REPO),
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
                "repo": str(REPO if REPO.exists() else LIVE_REPO),
                "snapshot": status_snapshot(REPO if REPO.exists() else LIVE_REPO),
            }
        )
    except Exception as exc:
        emit(
            {
                "wakeAgent": True,
                "status": "needs_agent",
                "stage": "unexpected_exception",
                "message": redact(repr(exc)),
                "repo": str(REPO if REPO.exists() else LIVE_REPO),
                "snapshot": status_snapshot(REPO if REPO.exists() else LIVE_REPO),
            }
        )
