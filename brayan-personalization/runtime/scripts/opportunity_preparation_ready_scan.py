#!/usr/bin/env python3
"""Dispatch independent Hermes opportunity-preparation sessions for ready opportunities.

Dispatcher-only responsibilities:
1. Scan ~/personal_vault/opportunities/*/opportunity.md for `preparation-ready` opportunities.
2. Require automation_route: opportunity-preparation.
3. Sort/select at most MAX_SESSIONS launchable opportunities.
4. Render ~/.hermes/agents/opportunity-preparation/prompt-template.md with opportunity fields.
5. Launch one independent Hermes session per selected opportunity.
6. Emit wake-gated JSON for the parent cron job.

Stable agent behavior lives in:
- ~/.hermes/skills/opportunities/opportunity-preparation-agent/SKILL.md
- ~/.hermes/agents/opportunity-preparation/prompt-template.md
"""
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
AGENT_DIR = HERMES_HOME / "agents" / "opportunity-preparation"
PROMPT_TEMPLATE_PATH = AGENT_DIR / "prompt-template.md"
STATE_DIR = HERMES_HOME / "state" / "opportunity_preparation_sessions"
LOG_DIR = HERMES_HOME / "logs" / "opportunity_preparation_sessions"
MAX_SESSIONS = 3
LOCK_TTL_HOURS = 18
SKILLS = "personal-vault-ops,opportunity-preparation-agent"
SOURCE_TAG = "opportunity-preparation-session"
READY_STATUS = "preparation-ready"
REQUIRED_AUTOMATION_ROUTE = "opportunity-preparation"
NULL_PACKET_VALUES = {"null", "none", "", "not-started"}


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
        return fm["title"]
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else fallback


def body_status(text: str) -> str:
    match = re.search(r"(?:posting\s+status|status):\s*`?([A-Za-z-]+)`?", text, re.I)
    return match.group(1).strip().lower() if match else ""


def resolve_packet_reference(value: str) -> Path | None:
    """Resolve a preparation_packet/Packet path only if it names preparation-packet.md."""
    raw = (value or "").strip().strip('"').strip("'")
    if raw.lower() in NULL_PACKET_VALUES:
        return None
    match = re.search(r"\[\[([^\]|#]+)", raw)
    ref = match.group(1).strip() if match else raw
    ref = ref.strip().strip('"').strip("'")
    if not ref or "preparation-packet" not in ref:
        return None
    ref_path = Path(ref)
    if not ref_path.suffix:
        ref_path = ref_path.with_suffix(".md")
    if not ref_path.is_absolute():
        ref_path = VAULT / ref_path
    return ref_path


def existing_packet_from_value(value: str) -> bool:
    packet_path = resolve_packet_reference(value)
    return bool(packet_path and packet_path.exists() and packet_path.name == "preparation-packet.md")


def has_existing_packet(path: Path, fm: dict[str, str], text: str) -> bool:
    expected_packet = path.parent / "application" / "preparation-packet.md"
    if expected_packet.exists():
        return True
    if existing_packet_from_value(fm.get("preparation_packet") or ""):
        return True
    # Only same-line values count. `\s` would cross into the next bullet.
    packet_line = re.search(r"Packet path:[ \t]*(\S.*)$", text, re.I | re.M)
    if packet_line and existing_packet_from_value(packet_line.group(1)):
        return True
    return False


def opportunity_record(path: Path, text: str, fm: dict[str, str]) -> dict[str, str]:
    return {
        "opportunity_path": str(path),
        "path": str(path),
        "stem": path.parent.name,
        "title": extract_title(text, fm, path.parent.name),
        "host": fm.get("host") or fm.get("company") or "unknown",
        "company": fm.get("company", "unknown"),
        "role": fm.get("role", "unknown"),
        "opportunity_kind": fm.get("opportunity_kind", "unknown"),
        "workflow_mode": fm.get("workflow_mode", "unknown"),
        "primary_artifact_focus": fm.get("primary_artifact_focus", "unknown"),
        "cv_relevance": fm.get("cv_relevance", "unknown"),
        "automation_route": fm.get("automation_route", "unknown"),
        "priority": fm.get("priority", "unknown"),
        "status": (fm.get("status") or body_status(text)).strip().lower() or "unknown",
        "source_url": fm.get("source_url", "unknown"),
        "application_url": fm.get("application_url", "unknown"),
        "form_inspection_status": fm.get("form_inspection_status", "unknown"),
        "preparation_packet": fm.get("preparation_packet", "unknown"),
        "job_work_automation_potential": fm.get("job_work_automation_potential", "unknown"),
        "application_process_complexity": fm.get("application_process_complexity", "unknown"),
    }


def collect_inventory() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (launchable_ready_opportunities, all opportunity records with skip reasons)."""
    ready: list[dict[str, str]] = []
    inventory: list[dict[str, str]] = []
    if not OPPORTUNITIES_DIR.exists():
        return ready, inventory

    for path in sorted(OPPORTUNITIES_DIR.glob("*/opportunity.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        record = opportunity_record(path, text, fm)
        packet_exists = has_existing_packet(path, fm, text)
        record["has_existing_packet"] = str(packet_exists).lower()
        if record["status"] != READY_STATUS:
            record["skip_reason"] = f"status is {record['status']}, not {READY_STATUS}"
        elif record["automation_route"] != REQUIRED_AUTOMATION_ROUTE:
            record["skip_reason"] = f"automation_route is {record['automation_route']}, not {REQUIRED_AUTOMATION_ROUTE}"
        elif packet_exists:
            record["skip_reason"] = "verified application/preparation-packet.md already exists"
        else:
            record["skip_reason"] = "launchable"
            ready.append(record)
        inventory.append(record)

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
        data.update({
            "lock_path": str(lock_path),
            "still_running": still_running,
            "fresh_lock": fresh,
            "age_hours": age_hours,
        })
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


def launch_opportunity(item: dict[str, str]) -> dict[str, object]:
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
        proc = subprocess.Popen(
            cmd,
            cwd=str(VAULT),
            stdin=subprocess.DEVNULL,
            stdout=stdout_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    lock_path.write_text(json.dumps({
        "opportunity": item,
        "pid": proc.pid,
        "launched_at": datetime.now(timezone.utc).isoformat(),
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "prompt_path": str(prompt_path),
        "log_path": str(stdout_path),
        "skills": SKILLS,
        "command": [cmd[0], "--skills", SKILLS, "chat", "-Q", "--source", SOURCE_TAG, "-q", "<rendered prompt>"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "path": item["opportunity_path"],
        "stem": item["stem"],
        "title": item["title"],
        "opportunity_kind": item["opportunity_kind"],
        "workflow_mode": item["workflow_mode"],
        "priority": item["priority"],
        "pid": proc.pid,
        "prompt_template_path": str(PROMPT_TEMPLATE_PATH),
        "prompt_path": str(prompt_path),
        "log_path": str(stdout_path),
        "lock_path": str(lock_path),
    }


def select_opportunities(ready: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    selected: list[dict[str, str]] = []
    skipped_active: list[dict[str, object]] = []
    for item in ready:
        lock = active_lock(item)
        if lock:
            skipped_active.append({
                "path": item["opportunity_path"],
                "stem": item["stem"],
                "title": item["title"],
                "priority": item["priority"],
                "lock": lock,
            })
            continue
        selected.append(item)
        if len(selected) >= MAX_SESSIONS:
            break
    return selected, skipped_active


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show selected opportunities without launching sessions")
    args = parser.parse_args()

    ready, inventory = collect_inventory()
    selected, skipped_active = select_opportunities(ready)
    launched: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    if not PROMPT_TEMPLATE_PATH.exists():
        errors.append({"path": str(PROMPT_TEMPLATE_PATH), "stem": "prompt-template", "error": "missing prompt template"})
    elif not args.dry_run:
        for item in selected:
            try:
                launched.append(launch_opportunity(item))
            except Exception as exc:  # keep one bad launch from blocking others
                errors.append({"path": item["opportunity_path"], "stem": item["stem"], "error": repr(exc)})

    status_counts = Counter(item.get("status", "unknown") for item in inventory)
    route_counts = Counter(item.get("automation_route", "unknown") for item in inventory)
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
        "opportunity_count": len(inventory),
        "status_counts": dict(sorted(status_counts.items())),
        "automation_route_counts": dict(sorted(route_counts.items())),
        "skip_counts": dict(sorted(skip_counts.items())),
        "ready_count": len(ready),
        "selected_count": len(selected),
        "launched_count": len(launched),
        "skipped_active_count": len(skipped_active),
        "error_count": len(errors),
        "ready_opportunities": ready,
        "selected_opportunities": selected,
        "launched_opportunities": launched,
        "skipped_active_opportunities": skipped_active,
        "non_launchable_opportunities": non_launchable,
        "errors": errors,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
