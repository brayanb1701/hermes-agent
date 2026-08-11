#!/usr/bin/env python3
"""Deterministic project hub/workspace scaffold helper for Brayan's project lifecycle."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

HOME = Path.home()
VAULT = HOME / "personal_vault"
WORKSPACE_ROOT = HOME / "projects"
TEMPLATE_DIR = VAULT / "_meta" / "templates"
TODAY = date.today().isoformat()


class RawYaml(str):
    """An existing YAML value block that must be rendered byte-for-byte."""


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm: dict[str, str] = {}
    lines = text[4:end].splitlines()
    key_line = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$")
    i = 0
    while i < len(lines):
        match = key_line.match(lines[i])
        if not match:
            i += 1
            continue
        key = match.group(1)
        first_value = match.group(2) or ""
        continuation: list[str] = []
        i += 1
        while i < len(lines) and not key_line.match(lines[i]):
            continuation.append(lines[i])
            i += 1
        if continuation:
            fm[key] = RawYaml("\n".join([first_value, *continuation]))
        else:
            fm[key] = first_value.strip().strip('"').strip("'")
    return fm, text[end + 5 :]


def yaml_scalar(value: Any) -> str:
    if isinstance(value, RawYaml):
        return str(value)
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[]" if not value else "[" + ", ".join(str(v) for v in value) + "]"
    text = str(value)
    if text == "" or text.lower() in {"null", "none"}:
        return "null" if text.lower() in {"null", "none"} else '""'
    if text == "[]" or (text.startswith("[") and text.endswith("]")):
        return text
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    if any(ch in text for ch in [":", "#", "[", "]", "{", "}", "|"]):
        return json.dumps(text, ensure_ascii=False)
    return text


def render_frontmatter(fm: dict[str, Any]) -> str:
    order = [
        "title", "created", "updated", "type", "status", "area", "priority", "tags", "sources",
        "objective", "next_action", "success_criteria", "activation_criteria", "stop_condition",
        "review_cadence", "last_meaningful_update", "external_workspace", "linked_opportunities",
        "linked_decisions", "closeout", "final_artifacts", "lessons", "paused", "pause_reason",
        "resume_condition", "next_review", "completed", "closed", "result_status", "result_type",
        "result_summary",
    ]
    lines = ["---"]
    seen: set[str] = set()
    for key in order:
        if key in fm:
            rendered = yaml_scalar(fm[key])
            first, *continuation = rendered.splitlines()
            lines.append(f"{key}: {first}" if first else f"{key}:")
            lines.extend(continuation)
            seen.add(key)
    for key, value in fm.items():
        if key not in seen:
            rendered = yaml_scalar(value)
            first, *continuation = rendered.splitlines()
            lines.append(f"{key}: {first}" if first else f"{key}:")
            lines.extend(continuation)
    lines.append("---")
    return "\n".join(lines) + "\n"


def slug_title(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-"))


def template_body(name: str) -> str:
    path = TEMPLATE_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def render_template(text: str, values: dict[str, Any]) -> str:
    rendered = text
    mapping = {**values}
    mapping.setdefault("YYYY-MM-DD", TODAY)
    for key, value in mapping.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    rendered = rendered.replace("{{Project Title}}", str(mapping.get("Project Title", mapping.get("title", "Project"))))
    rendered = rendered.replace("{{YYYY-MM-DD}}", TODAY)
    return rendered


def strip_template_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip()
    return text


def load_project(path: Path) -> tuple[dict[str, str], str]:
    if not path.exists():
        return {}, ""
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def save_project(path: Path, fm: dict[str, Any], body: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_frontmatter(fm) + "\n" + body.lstrip("\n"), encoding="utf-8")


def ensure_project_readme(path: Path, mode: str, dry_run: bool) -> tuple[dict[str, Any], str, list[str]]:
    created: list[str] = []
    fm, body = load_project(path)
    slug = path.parent.name
    title = fm.get("title") or slug_title(slug)
    if not path.exists():
        fm = {
            "title": title,
            "created": TODAY,
            "updated": TODAY,
            "type": "project",
            "status": "seed",
            "area": "other",
            "priority": "unknown",
            "tags": "[project]",
            "sources": "[]",
            "objective": f"Advance {title} to a useful, reviewable outcome.",
            "next_action": "Define the next concrete experiment or activation requirement.",
            "success_criteria": "[]",
            "activation_criteria": "[\"Objective, success criteria, stop condition, and next action are concrete\"]",
            "stop_condition": "Archive if the idea is superseded, no longer valuable, or lacks an actionable path.",
            "review_cadence": "5d",
            "last_meaningful_update": "null",
            "external_workspace": "null",
            "linked_opportunities": "[]",
            "linked_decisions": "[]",
            "closeout": "null",
            "final_artifacts": "[]",
            "lessons": "[]",
        }
        body = f"# {title}\n\n## Objective\n\n{fm['objective']}\n\n## Why this matters\n\n## Current status\n- Status: seed\n- Priority: unknown\n- Current next action: {fm['next_action']}\n- Last meaningful update: null\n\n## Success criteria\n- Minimum useful result:\n- Strong result:\n- Stretch result:\n\n## Activation / stop / pause conditions\n- Activation criteria: {fm['activation_criteria']}\n- Stop condition: {fm['stop_condition']}\n- Pause condition:\n- Kill criteria:\n\n## Workspaces and artifacts\n- Vault control note: [[projects/{slug}/README]]\n- External workspace: null\n- Workspace status:\n- Workspace changelog:\n\n## Plan / next actions\n- [ ] {fm['next_action']}\n\n## Review log\n- {TODAY} — created\n"
        created.append(str(path))
    fm.setdefault("title", title)
    fm.setdefault("created", TODAY)
    fm["updated"] = TODAY
    fm.setdefault("type", "project")
    fm.setdefault("area", "other")
    fm.setdefault("priority", "unknown")
    fm.setdefault("tags", "[project]")
    fm.setdefault("sources", "[]")
    fm.setdefault("objective", f"Advance {title} to a useful, reviewable outcome.")
    fm.setdefault("next_action", "Review project hub and define the next executable action.")
    fm.setdefault("stop_condition", "Close/archive when success criteria are met, the project is superseded, or continued work is no longer worth attention.")
    fm.setdefault("review_cadence", "5d")
    fm.setdefault("linked_opportunities", "[]")
    fm.setdefault("linked_decisions", "[]")
    fm.setdefault("closeout", "null")
    fm.setdefault("final_artifacts", "[]")
    fm.setdefault("lessons", "[]")
    if mode == "seed":
        fm["status"] = "seed"
        fm.setdefault("activation_criteria", "[\"Objective, success criteria, stop condition, and next action are concrete\"]")
        fm["external_workspace"] = "null"
        fm.setdefault("success_criteria", "[]")
        fm.setdefault("last_meaningful_update", "null")
    return fm, body, created


def next_review(last: str, cadence: str) -> str:
    try:
        start = date.fromisoformat(last if re.match(r"^\d{4}-\d{2}-\d{2}$", last or "") else TODAY)
    except Exception:
        start = date.today()
    match = re.match(r"^(\d+)d$", str(cadence or "5d"))
    days = int(match.group(1)) if match else 5
    return (start + timedelta(days=days)).isoformat()


def project_values(path: Path, fm: dict[str, Any]) -> dict[str, Any]:
    slug = path.parent.name
    title = fm.get("title") or slug_title(slug)
    last = fm.get("last_meaningful_update") or fm.get("updated") or TODAY
    return {
        "slug": slug,
        "Project Title": title,
        "title": title,
        "YYYY-MM-DD": TODAY,
        "objective": fm.get("objective", ""),
        "next_action": fm.get("next_action", ""),
        "success_criteria": fm.get("success_criteria", "[]"),
        "stop_condition": fm.get("stop_condition", ""),
        "review_cadence": fm.get("review_cadence", "5d"),
        "last_meaningful_update": last,
        "next_review": next_review(str(last), str(fm.get("review_cadence", "5d"))),
    }


def create_from_template(path: Path, template_name: str, target: Path, values: dict[str, Any], result: dict[str, Any], dry_run: bool, force: bool) -> None:
    text = template_body(template_name)
    if not text:
        result["errors"].append(f"missing template: {TEMPLATE_DIR / template_name}")
        return
    rendered = render_template(text, values)
    if target.exists() and not force:
        result["skipped_existing"].append(str(target))
        return
    if dry_run:
        result["would_create"].append(str(target))
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        result["created"].append(str(target))


def activate_project(path: Path, result: dict[str, Any], dry_run: bool, force: bool) -> None:
    fm, body, created = ensure_project_readme(path, "activate", dry_run)
    result["created"].extend([] if dry_run else created)
    result["would_create"].extend(created if dry_run else [])
    required = ["objective", "next_action", "success_criteria", "stop_condition", "review_cadence"]
    missing = [key for key in required if not str(fm.get(key, "")).strip() or str(fm.get(key)).lower() in {"null", "none", "[]"}]
    if missing:
        result["errors"].append(f"cannot activate {path}: missing {', '.join(missing)}")
        return
    slug = path.parent.name
    workspace = Path(str(fm.get("external_workspace") or WORKSPACE_ROOT / slug))
    if str(workspace).lower() in {"null", "none", ""}:
        workspace = WORKSPACE_ROOT / slug
    fm["status"] = "active"
    fm["external_workspace"] = str(workspace)
    fm.setdefault("last_meaningful_update", fm.get("updated") or TODAY)
    save_project(path, fm, body, dry_run)
    if dry_run:
        if not workspace.exists():
            result["would_create"].append(str(workspace))
    else:
        workspace.mkdir(parents=True, exist_ok=True)
        if str(workspace) not in result["created"] and str(workspace) not in result["skipped_existing"]:
            result["created" if not workspace.exists() else "skipped_existing"].append(str(workspace))
    values = project_values(path, fm)
    create_from_template(path, "project-workspace-status-template.md", workspace / "PROJECT_STATUS.md", values, result, dry_run, force)
    create_from_template(path, "project-workspace-changelog-template.md", workspace / "PROJECT_CHANGELOG.md", values, result, dry_run, force)


def seed_project(path: Path, result: dict[str, Any], dry_run: bool, force: bool) -> None:
    fm, body, created = ensure_project_readme(path, "seed", dry_run)
    result["created"].extend([] if dry_run else created)
    result["would_create"].extend(created if dry_run else [])
    save_project(path, fm, body, dry_run)


def closeout_or_reopen(path: Path, kind: str, result: dict[str, Any], dry_run: bool, force: bool) -> None:
    fm, _ = load_project(path)
    values = project_values(path, fm)
    slug = path.parent.name
    workspace = Path(str(fm.get("external_workspace") or WORKSPACE_ROOT / slug))
    if str(workspace).lower() in {"null", "none", ""}:
        workspace = WORKSPACE_ROOT / slug
    if dry_run and not workspace.exists():
        result["would_create"].append(str(workspace))
    elif not dry_run:
        workspace.mkdir(parents=True, exist_ok=True)
    if kind == "closeout":
        create_from_template(path, "project-workspace-closeout-template.md", workspace / "PROJECT_CLOSEOUT.md", values, result, dry_run, force)
    else:
        create_from_template(path, "project-workspace-reopen-template.md", workspace / "PROJECT_REOPEN.md", values, result, dry_run, force)


def active_projects(vault: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted((vault / "projects").glob("*/README.md")):
        fm, _ = load_project(path)
        if fm.get("status") == "active":
            out.append(path)
    return out


def main() -> None:
    global VAULT, WORKSPACE_ROOT, TEMPLATE_DIR
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", help="Path to projects/<slug>/README.md")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--closeout", action="store_true")
    parser.add_argument("--reopen", action="store_true")
    parser.add_argument("--all-active", action="store_true")
    parser.add_argument("--vault", default=str(VAULT))
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    VAULT = Path(args.vault).expanduser().resolve()
    WORKSPACE_ROOT = Path(args.workspace_root).expanduser().resolve()
    TEMPLATE_DIR = VAULT / "_meta" / "templates"

    modes = [args.seed, args.activate, args.closeout, args.reopen]
    if args.all_active:
        mode = "activate"
        projects = active_projects(VAULT)
    else:
        if sum(bool(x) for x in modes) != 1:
            raise SystemExit("Choose exactly one of --seed/--activate/--closeout/--reopen, or use --all-active")
        if not args.project:
            raise SystemExit("--project is required unless --all-active is used")
        projects = [Path(args.project).expanduser().resolve()]
        mode = "seed" if args.seed else "activate" if args.activate else "closeout" if args.closeout else "reopen"

    summary = {
        "wakeAgent": False,
        "script": "project_scaffold.py",
        "dry_run": args.dry_run,
        "mode": mode,
        "vault": str(VAULT),
        "workspace_root": str(WORKSPACE_ROOT),
        "projects": [str(p) for p in projects],
        "created": [],
        "would_create": [],
        "skipped_existing": [],
        "errors": [],
    }
    for project in projects:
        if mode == "seed":
            seed_project(project, summary, args.dry_run, args.force)
        elif mode == "activate":
            activate_project(project, summary, args.dry_run, args.force)
        elif mode == "closeout":
            closeout_or_reopen(project, "closeout", summary, args.dry_run, args.force)
        elif mode == "reopen":
            closeout_or_reopen(project, "reopen", summary, args.dry_run, args.force)
    summary["wakeAgent"] = bool(summary["errors"])
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
