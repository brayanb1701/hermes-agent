#!/usr/bin/env python3
"""Dispatch independent Hermes opportunity-closing sessions for live closeout inputs."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
VAULT = HOME / "personal_vault"
HERMES_HOME = HOME / ".hermes"
OPPORTUNITIES_DIR = VAULT / "opportunities"
AGENT_DIR = HERMES_HOME / "agents" / "opportunity-closing"
PROMPT_TEMPLATE_PATH = AGENT_DIR / "prompt-template.md"
STATE_DIR = HERMES_HOME / "state" / "opportunity_closing_sessions"
LOG_DIR = HERMES_HOME / "logs" / "opportunity_closing_sessions"
MAX_SESSIONS = 3
LOCK_TTL_HOURS = 12
SKILLS = "personal-vault-ops,opportunity-closing-agent"
SOURCE_TAG = "opportunity-closing-session"
VALID_PROPOSED_STATUSES = {"applied", "archived"}
SKIP_STATUSES = {"example", "complete", "paused"}


def configure_vault(vault: Path) -> None:
    global VAULT, OPPORTUNITIES_DIR
    VAULT = vault
    OPPORTUNITIES_DIR = VAULT / "opportunities"


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def extract_title(text: str, fm: dict[str, str], fallback: str) -> str:
    if fm.get("title"):
        title = fm["title"]
        return title[:-len(" Closeout Input")] if title.endswith(" Closeout Input") else title
    match = re.search(r"^#\s+(.+?)(?:\s+Closeout Input)?$", text, re.M)
    return match.group(1).strip() if match else fallback


def resolve_wikilink_path(value: str, vault: Path) -> Path | None:
    raw = (value or "").strip()
    if not raw:
        return None
    match = re.search(r"\[\[([^\]|#]+)", raw)
    ref = match.group(1).strip() if match else raw.strip('"').strip("'")
    if not ref:
        return None
    path = Path(ref)
    if not path.suffix:
        path = path.with_suffix(".md")
    if not path.is_absolute():
        path = vault / path
    return path


def opportunity_path_for(closeout_path: Path, fm: dict[str, str], vault: Path) -> Path:
    explicit = resolve_wikilink_path(fm.get("opportunity", ""), vault)
    if explicit:
        return explicit
    return closeout_path.parent / "opportunity.md"


def body_field(text: str, label: str, default: str = "unknown") -> str:
    match = re.search(rf"^-\s*{re.escape(label)}:\s*(.+)$", text, re.I | re.M)
    if match:
        value = match.group(1).strip().strip('`')
        return value or default
    return default


def opportunity_fm(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))


def closeout_record(path: Path, vault: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    opp_path = opportunity_path_for(path, fm, vault)
    opp = opportunity_fm(opp_path)
    stem = path.parent.name
    title = extract_title(text, fm, opp.get("title") or stem)
    proposed_status = (fm.get("proposed_status") or body_field(text, "Proposed status", "unknown")).lower().strip()
    proposed_result_status = (fm.get("proposed_result_status") or body_field(text, "Proposed result_status", "unknown")).lower().strip()
    status = (fm.get("status") or "unknown").lower().strip()
    priority = opp.get("priority", "unknown")
    return {
        "closeout_input_path": str(path),
        "opportunity_path": str(opp_path),
        "stem": stem,
        "title": title,
        "status": status,
        "priority": priority,
        "proposed_status": proposed_status,
        "proposed_result_status": proposed_result_status,
        "project_closeout_check": fm.get("project_closeout_check") or body_field(text, "Classification", "unknown"),
    }


def collect_inventory(vault: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    ready: list[dict[str, str]] = []
    inventory: list[dict[str, str]] = []
    opp_dir = vault / "opportunities"
    if not opp_dir.exists():
        return ready, inventory
    for path in sorted(opp_dir.glob("*/closeout-input.md")):
        if path.name != "closeout-input.md":
            continue
        try:
            record = closeout_record(path, vault)
            opp_path = Path(record["opportunity_path"])
            if record["status"] != "pending":
                if record["status"] in SKIP_STATUSES:
                    record["skip_reason"] = f"status is {record['status']}"
                else:
                    record["skip_reason"] = f"status is {record['status']}, not pending"
            elif not opp_path.exists():
                record["skip_reason"] = "opportunity.md missing"
            elif record["proposed_status"] not in VALID_PROPOSED_STATUSES:
                record["skip_reason"] = f"proposed_status is {record['proposed_status']}, not applied|archived"
            else:
                record["skip_reason"] = "launchable"
                ready.append(record)
            inventory.append(record)
        except Exception as exc:
            inventory.append({"closeout_input_path": str(path), "stem": path.parent.name, "status": "error", "skip_reason": "parse-error", "error": repr(exc)})
    priority_rank = {"p0": 0, "p1": 1, "p2": 2, "p3": 3}
    ready.sort(key=lambda item: (priority_rank.get(item.get("priority", "").lower(), 9), item["stem"]))
    return ready, inventory


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def active_lock(item: dict[str, str]) -> dict[str, object] | None:
    lock_path = STATE_DIR / f"{item['stem']}.json"
    if not lock_path.exists():
        return None
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    pid = int(data.get("pid") or 0)
    still_running = pid_is_running(pid)
    fresh = False
    age_hours = None
    try:
        launched_at = str(data.get("launched_at") or "")
        dt = datetime.fromisoformat(launched_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600
        fresh = age_hours < LOCK_TTL_HOURS
    except Exception:
        pass
    if still_running or fresh:
        data.update({"lock_path": str(lock_path), "still_running": still_running, "fresh_lock": fresh, "age_hours": age_hours})
        return data
    return None


def render_template(template: str, item: dict[str, str]) -> str:
    rendered = template
    for key, value in item.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    unresolved = sorted(set(re.findall(r"{{\s*([A-Za-z0-9_]+)\s*}}", rendered)))
    if unresolved:
        raise ValueError(f"Unresolved prompt placeholders: {', '.join(unresolved)}")
    return rendered


def build_prompt(item: dict[str, str]) -> str:
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return render_template(template, item)


def launch_closeout(item: dict[str, str]) -> dict[str, object]:
    hermes = shutil.which("hermes") or str(HOME / ".local" / "bin" / "hermes")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(item)
    prompt_path = STATE_DIR / f"{item['stem']}.{timestamp}.prompt.txt"
    stdout_path = LOG_DIR / f"{item['stem']}.{timestamp}.log"
    lock_path = STATE_DIR / f"{item['stem']}.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    cmd = [hermes, "--skills", SKILLS, "chat", "-Q", "--source", SOURCE_TAG, "-q", prompt]
    with stdout_path.open("ab") as stdout_fh:
        proc = subprocess.Popen(cmd, cwd=str(VAULT), stdin=subprocess.DEVNULL, stdout=stdout_fh, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    lock_path.write_text(json.dumps({
        "closeout": item,
        "pid": proc.pid,
        "launched_at": datetime.now(timezone.utc).isoformat(),
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "prompt_path": str(prompt_path),
        "log_path": str(stdout_path),
        "skills": SKILLS,
        "command": [cmd[0], "--skills", SKILLS, "chat", "-Q", "--source", SOURCE_TAG, "-q", "<rendered prompt>"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "closeout_input_path": item["closeout_input_path"],
        "opportunity_path": item["opportunity_path"],
        "stem": item["stem"],
        "title": item["title"],
        "proposed_status": item["proposed_status"],
        "proposed_result_status": item["proposed_result_status"],
        "priority": item["priority"],
        "pid": proc.pid,
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "prompt_path": str(prompt_path),
        "log_path": str(stdout_path),
        "lock_path": str(lock_path),
    }


def select_closeouts(ready: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    selected: list[dict[str, str]] = []
    skipped_active: list[dict[str, object]] = []
    for item in ready:
        lock = active_lock(item)
        if lock:
            skipped_active.append({"closeout_input_path": item["closeout_input_path"], "stem": item["stem"], "title": item["title"], "priority": item["priority"], "lock": lock})
            continue
        selected.append(item)
        if len(selected) >= MAX_SESSIONS:
            break
    return selected, skipped_active


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show selected closeouts without launching sessions")
    parser.add_argument("--vault", default=str(VAULT), help="Vault path for testability")
    args = parser.parse_args()
    configure_vault(Path(args.vault).expanduser().resolve())

    ready, inventory = collect_inventory(VAULT)
    selected, skipped_active = select_closeouts(ready)
    launched: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    if selected and not PROMPT_TEMPLATE_PATH.exists():
        errors.append({"path": str(PROMPT_TEMPLATE_PATH), "stem": "prompt-template", "error": "missing prompt template"})
    elif not args.dry_run:
        for item in selected:
            try:
                launched.append(launch_closeout(item))
            except Exception as exc:
                errors.append({"path": item["closeout_input_path"], "stem": item["stem"], "error": repr(exc)})

    status_counts = Counter(item.get("status", "unknown") for item in inventory)
    skip_counts = Counter(item.get("skip_reason", "unknown") for item in inventory)
    non_launchable = [item for item in inventory if item.get("skip_reason") != "launchable"]
    print(json.dumps({
        "wakeAgent": bool(errors or launched),
        "dispatch_only": True,
        "dry_run": args.dry_run,
        "vault": str(VAULT),
        "opportunities_dir": str(OPPORTUNITIES_DIR),
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "skills": SKILLS,
        "state_dir": str(STATE_DIR),
        "log_dir": str(LOG_DIR),
        "max_sessions": MAX_SESSIONS,
        "closeout_input_count": len(inventory),
        "status_counts": dict(sorted(status_counts.items())),
        "skip_counts": dict(sorted(skip_counts.items())),
        "ready_count": len(ready),
        "selected_count": len(selected),
        "launched_count": len(launched),
        "skipped_active_count": len(skipped_active),
        "error_count": len(errors),
        "ready_closeouts": ready,
        "selected_closeouts": selected,
        "launched_closeouts": launched,
        "skipped_active_closeouts": skipped_active,
        "non_launchable_closeouts": non_launchable,
        "errors": errors,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
