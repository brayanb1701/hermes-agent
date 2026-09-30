#!/usr/bin/env python3
"""Wake-gated scanner/dispatcher for Brayan's project-management workflow."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

HOME = Path.home()
VAULT = Path(os.environ.get("HERMES_VAULT_ROOT", HOME / "personal_vault")).expanduser()
HERMES_HOME = Path(os.environ.get("HERMES_HOME", HOME / ".hermes")).expanduser()
PROJECTS_DIR = VAULT / "projects"
WORKSPACE_ROOT = HOME / "projects"
AGENT_DIR = HERMES_HOME / "agents" / "project-management"
PROMPT_TEMPLATE_PATH = AGENT_DIR / "prompt-template.md"
STATE_DIR = HERMES_HOME / "state" / "project_management_sessions"
LOG_DIR = HERMES_HOME / "logs" / "project_management_sessions"
MAX_SESSIONS = 3

SKILLS = "personal-vault-ops,personal-project-management"
SOURCE_TAG = "project-management-session"
DEFAULT_STALE_DAYS = 5

PRIORITY_RANK = {"p0": 0, "p1": 1, "p2": 2, "p3": 3, "unknown": 9, "": 9}
MODE_SEVERITY = {"closeout": 0, "reopen": 1, "audit-fix-proposal": 2, "pause": 3, "review": 4, "activate": 5}


def configure(vault: Path, workspace_root: Path) -> None:
    global VAULT, PROJECTS_DIR, WORKSPACE_ROOT
    VAULT = vault
    PROJECTS_DIR = VAULT / "projects"
    WORKSPACE_ROOT = workspace_root


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith(" ") or line.startswith("-") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip().strip('"').strip("'")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def cadence_days(value: str | None) -> int:
    match = re.match(r"^(\d+)d$", (value or "").strip())
    return int(match.group(1)) if match else DEFAULT_STALE_DAYS


def due_by_cadence(last: str | None, cadence: str | None) -> bool:
    last_date = parse_date(last)
    if not last_date:
        return True
    return (date.today() - last_date).days >= cadence_days(cadence)


def resolve_workspace(slug: str, fm: dict[str, str]) -> Path:
    raw = (fm.get("external_workspace") or "").strip()
    if raw and raw.lower() not in {"null", "none", "[]"}:
        return Path(raw).expanduser()
    return WORKSPACE_ROOT / slug


def file_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        fm = parse_frontmatter(read(path))
        return (fm.get("status") or "unknown").lower()
    except Exception:
        return "parse-error"


def latest_type(text: str) -> str:
    matches = re.findall(r"(?im)^-\s*Type:\s*([A-Za-z0-9_-]+)", text)
    return matches[-1].lower() if matches else ""


def dashboard_text() -> str:
    path = PROJECTS_DIR / "dashboard.md"
    return read(path) if path.exists() else ""


def backlog_text() -> str:
    path = PROJECTS_DIR / "backlog.md"
    return read(path) if path.exists() else ""


def dashboard_has(slug: str) -> bool:
    return f"projects/{slug}/README" in dashboard_text()


def backlog_has(slug: str) -> bool:
    return f"projects/{slug}/README" in backlog_text()


def activation_requested(text: str, fm: dict[str, str]) -> bool:
    if (fm.get("activation_requested") or "").lower() == "true":
        return True
    return bool(re.search(r"(?i)activation[_ -]requested:\s*true|pending activation|activate this project", text))


def record(path: Path, mode: str, reason: str, signal_file: str = "") -> dict[str, Any]:
    text = read(path)
    fm = parse_frontmatter(text)
    slug = path.parent.name
    workspace = resolve_workspace(slug, fm)
    return {
        "mode": mode,
        "slug": slug,
        "title": fm.get("title") or slug.replace("-", " ").title(),
        "vault_project_path": str(path),
        "workspace_path": str(workspace),
        "trigger_reason": reason,
        "status": fm.get("status", "unknown"),
        "priority": fm.get("priority", "unknown"),
        "area": fm.get("area", "unknown"),
        "review_cadence": fm.get("review_cadence", "5d"),
        "last_meaningful_update": fm.get("last_meaningful_update", "unknown"),
        "signal_file": signal_file,
    }


def latest_review_date(text: str) -> date | None:
    return max((day for day, _ in review_entries(text) if day <= date.today()), default=None)


def collect_inventory(vault: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    if not PROJECTS_DIR.exists():
        return ready, inventory
    for path in sorted(PROJECTS_DIR.glob("*/README.md")):
        try:
            text = read(path)
            fm = parse_frontmatter(text)
            slug = path.parent.name
            status = (fm.get("status") or "unknown").lower()
            workspace = resolve_workspace(slug, fm)
            item = {
                "slug": slug,
                "path": str(path),
                "status": status,
                "priority": fm.get("priority", "unknown"),
                "area": fm.get("area", "unknown"),
                "workspace_path": str(workspace),
                "skip_reason": "not selected",
            }
            selected: dict[str, Any] | None = None
            if status == "active":
                reviewed = latest_review_date(text)
                hub_next = parse_date(fm.get('next_review'))
                missing = []
                if not workspace.exists():
                    missing.append("workspace")
                status_path = workspace / "PROJECT_STATUS.md"
                changelog_path = workspace / "PROJECT_CHANGELOG.md"
                if not status_path.exists():
                    missing.append("PROJECT_STATUS.md")
                if not changelog_path.exists():
                    missing.append("PROJECT_CHANGELOG.md")
                if missing:
                    selected = record(path, "audit-fix-proposal", "active project missing " + ", ".join(missing), str(workspace))
                elif not dashboard_has(slug) or backlog_has(slug):
                    selected = record(path, "audit-fix-proposal", "dashboard/backlog membership mismatch", str(path))
                closeout = workspace / "PROJECT_CLOSEOUT.md"
                reopen = workspace / "PROJECT_REOPEN.md"
                if closeout.exists() and file_status(closeout) == "pending":
                    selected = record(path, "closeout", "workspace PROJECT_CLOSEOUT.md pending", str(closeout))
                elif reopen.exists() and file_status(reopen) == "pending":
                    selected = record(path, "reopen", "workspace PROJECT_REOPEN.md pending", str(reopen))
                elif changelog_path.exists():
                    ctext = read(changelog_path)
                    cfm = parse_frontmatter(ctext)
                    nrd = parse_date(cfm.get("next_review"))
                    ltype = latest_type(ctext)
                    if ltype in {"pause", "paused"} or (cfm.get("status") or "").lower() == "paused":
                        selected = record(path, "pause", "changelog indicates pause", str(changelog_path))
                    elif ltype in {"resume", "reopen-request", "reopen"}:
                        selected = record(path, "reopen", "changelog indicates resume/reopen request", str(changelog_path))
                    elif ltype in {"blocker", "blocked"}:
                        selected = record(path, "review", "changelog indicates blocker", str(changelog_path))
                    elif nrd and nrd <= date.today() and (reviewed is None or nrd > reviewed):
                        selected = record(path, "review", "workspace next_review is due", str(changelog_path))
                if selected is None and hub_next and hub_next <= date.today() and (reviewed is None or hub_next > reviewed):
                    selected = record(path, 'review', 'project next_review is due', str(path))
                cadence_base = max(filter(None, (parse_date(fm.get('last_meaningful_update')), reviewed)), default=None)
                if (selected is None and not (hub_next and hub_next > date.today())
                        and due_by_cadence(cadence_base.isoformat() if cadence_base else None, fm.get('review_cadence'))):
                    selected = record(path, "review", "active project review cadence due", str(path))
            elif status == "paused":
                nrd = parse_date(fm.get("next_review"))
                if nrd and nrd <= date.today():
                    selected = record(path, "review", "paused project next_review is due", str(path))
                elif dashboard_has(slug) or not backlog_has(slug):
                    selected = record(path, "audit-fix-proposal", "paused project register membership mismatch", str(path))
            elif status == "seed":
                if activation_requested(text, fm):
                    selected = record(path, "activate", "seed project has activation requested", str(path))
                elif dashboard_has(slug) or not backlog_has(slug):
                    selected = record(path, "audit-fix-proposal", "seed project register membership mismatch", str(path))
            elif status in {"complete", "archived"}:
                if dashboard_has(slug) or backlog_has(slug):
                    selected = record(path, "audit-fix-proposal", "finalized project still appears in active/backlog surfaces", str(path))
            else:
                selected = record(path, "audit-fix-proposal", f"unsupported project status {status!r}", str(path))
            if selected:
                item["skip_reason"] = "launchable"
                item["selected_mode"] = selected["mode"]
                item["trigger_reason"] = selected["trigger_reason"]
                ready.append(selected)
            inventory.append(item)
        except Exception as exc:
            inventory.append({"slug": path.parent.name, "path": str(path), "status": "error", "skip_reason": "parse-error", "error": repr(exc)})
    ready.sort(key=lambda item: (PRIORITY_RANK.get(str(item.get("priority", "")).lower(), 9), MODE_SEVERITY.get(item["mode"], 9), item["slug"]))
    return ready, inventory


def render_template(template: str, item: dict[str, Any]) -> str:
    rendered = template
    for key, value in item.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    unresolved = sorted(set(re.findall(r"{{\s*([A-Za-z0-9_]+)\s*}}", rendered)))
    if unresolved:
        raise ValueError(f"Unresolved prompt placeholders: {', '.join(unresolved)}")
    return rendered


def build_prompt(item: dict[str, Any]) -> str:
    return render_template(PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8"), item)


def review_entries(text: str) -> list[tuple[date, str]]:
    """One parser for scheduling and persistence, matching retention's format."""
    from project_review_history_retention import SECTION_RE, NEXT_H2_RE, HEADING_ENTRY_RE, BULLET_ENTRY_RE
    entries = []
    for section in SECTION_RE.finditer(text):
        end = NEXT_H2_RE.search(text, section.end())
        body = text[section.end():end.start() if end else len(text)]
        headings = list(HEADING_ENTRY_RE.finditer(body))
        if headings:
            for index, match in enumerate(headings):
                day = parse_date(match.group(1))
                if day:
                    stop = headings[index + 1].start() if index + 1 < len(headings) else len(body)
                    entries.append((day, body[match.start():stop].strip()))
        else:
            for line in body.splitlines():
                match = BULLET_ENTRY_RE.match(line)
                if match and (day := parse_date(match.group(1))):
                    entries.append((day, line.strip()))
    return entries


def review_entries_today(text: str) -> set[str]:
    return {entry for day, entry in review_entries(text) if day == date.today()}


def launch_project(item: dict[str, Any]) -> dict[str, Any]:
    hermes = shutil.which("hermes") or str(HOME / ".local" / "bin" / "hermes")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(item) + f"\nOnly writable vault root: {VAULT}. Honor HERMES_VAULT_ROOT in every helper and descendant. Never publish, modify the canonical checkout, or leave background writers."
    prompt_path = STATE_DIR / f"{item['slug']}.{timestamp}.prompt.txt"
    stdout_path = LOG_DIR / f"{item['slug']}.{timestamp}.log"
    hub = Path(item['vault_project_path'])
    surfaces = [hub, *(PROJECTS_DIR / name for name in ('dashboard.md', 'backlog.md', 'finished.md'))]
    before = {path: read(path) if path.exists() else None for path in surfaces}
    before_entries = review_entries_today(before[hub] or '')
    before_key = (item['mode'], item['trigger_reason'])
    prompt_path.write_text(prompt, encoding="utf-8")
    cmd = [hermes, "--skills", SKILLS, "chat", "-Q", "--source", SOURCE_TAG, "-q", prompt]
    with stdout_path.open("ab") as stdout_fh:
        proc = subprocess.Popen(cmd, cwd=str(VAULT), stdin=subprocess.DEVNULL, stdout=stdout_fh, stderr=subprocess.STDOUT, start_new_session=False, close_fds=True)
    # Foreground completion is part of the parent ownership transaction.
    returncode = proc.wait()
    after = {path: read(path) if path.exists() else None for path in surfaces}
    ready, inventory = collect_inventory(VAULT)
    current = next((entry for entry in ready if entry['slug'] == item['slug']), None)
    after_key = (current['mode'], current['trigger_reason']) if current else None
    new_entry = bool(review_entries_today(after[hub] or '') - before_entries)
    persisted = new_entry or (item['mode'] != 'review' and after != before and after_key != before_key)
    scan_error = any(entry.get('status') == 'error' and entry['slug'] == item['slug'] for entry in inventory)
    if returncode:
        outcome = f'child-exit-{returncode}'
    elif scan_error or not after[hub] or not persisted:
        outcome = 'no-review-evidence'
    else:
        outcome = 'ok' if after_key != before_key else 'ok-still-due'
    # Evaluate child evidence before pruning: scanner housekeeping is not proof
    # that the child successfully saved its review.
    if after[hub]:
        from project_review_history_retention import prune_project
        prune_project(hub)
    metadata = parse_frontmatter(after[hub] or '')
    return {**item, 'pid': proc.pid, 'prompt_path': str(prompt_path),
            'log_path': str(stdout_path), 'outcome': outcome,
            'next_review': metadata.get('next_review'),
            'last_meaningful_update': metadata.get('last_meaningful_update'),
            'retry_warning': 'selection advanced without saved review; will not auto-retry' if not persisted and after_key != before_key else None,
            'summary': read(stdout_path)[-1500:]}


def select_projects(ready: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Children finish synchronously under the owner's global writer lock.
    return ready[:MAX_SESSIONS]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show selected projects without launching sessions")
    parser.add_argument("--vault", default=str(VAULT), help="Vault path for testability")
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT), help="Workspace root path for testability")
    args = parser.parse_args()
    configure(Path(args.vault).expanduser().resolve(), Path(args.workspace_root).expanduser().resolve())
    if not args.dry_run:
        from vault_ownership_common import load_contract
        contract = load_contract()
        root = os.environ.get('HERMES_VAULT_ROOT')
        worktrees = Path(contract['state_dir']).resolve() / 'worktrees'
        if (not root or Path(root).expanduser().resolve() != VAULT
                or not VAULT.is_relative_to(worktrees)
                or VAULT in {Path(contract['repo_path']).resolve(), Path(contract['vault_path']).resolve()}):
            raise SystemExit('Live project scan requires an ownership worktree; use --dry-run or the managed cron job.')

    ready, inventory = collect_inventory(VAULT)
    selected = select_projects(ready)
    launched: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if selected and not PROMPT_TEMPLATE_PATH.exists():
        errors.append({"path": str(PROMPT_TEMPLATE_PATH), "slug": "prompt-template", "error": "missing prompt template"})
    elif not args.dry_run:
        for item in selected:
            try:
                launched.append(launch_project(item))
            except Exception as exc:
                errors.append({"path": item["vault_project_path"], "slug": item["slug"], "error": repr(exc)})

    if not args.dry_run and selected:
        failures = [item for item in launched if item['outcome'] not in {'ok', 'ok-still-due'}]
        if failures or errors:
            print('[CRON_FAILURE]')
        print('Project management: persisted results checked by the scanner.')
        for item in launched:
            print(f"- {item['slug']} ({item['mode']}): {item['outcome']}; next_review={item['next_review'] or 'unset'}; trigger={item['trigger_reason']}")
            if item['retry_warning']:
                print('  WARNING: ' + item['retry_warning'])
            if item['summary'].strip():
                print(item['summary'].strip())
        for error in errors:
            print(f"- {error['slug']}: {error['error']}")
        print(f'Result: {len(launched) - len(failures)} verified, {len(failures) + len(errors)} failed.')
        return

    status_counts = Counter(item.get("status", "unknown") for item in inventory)
    mode_counts = Counter(item.get("selected_mode", "not-selected") for item in inventory)
    print(json.dumps({
        "wakeAgent": bool(errors or launched),
        "dispatch_only": True,
        "dry_run": args.dry_run,
        "vault": str(VAULT),
        "projects_dir": str(PROJECTS_DIR),
        "workspace_root": str(WORKSPACE_ROOT),
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "skills": SKILLS,
        "state_dir": str(STATE_DIR),
        "log_dir": str(LOG_DIR),
        "max_sessions": MAX_SESSIONS,
        "project_count": len(inventory),
        "status_counts": dict(sorted(status_counts.items())),
        "mode_counts": dict(sorted(mode_counts.items())),
        "ready_count": len(ready),
        "selected_count": len(selected),
        "launched_count": len(launched),

        "error_count": len(errors),
        "ready_projects": ready,
        "selected_projects": selected,
        "launched_projects": launched,

        "inventory": inventory,
        "errors": errors,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
