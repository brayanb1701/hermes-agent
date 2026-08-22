#!/usr/bin/env python3
"""Report-only audit for Brayan's project lifecycle state."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from vault_generated_retention import apply_retention

HOME = Path.home()
VAULT = HOME / "personal-vault"
WORKSPACE_ROOT = HOME / "projects"
HERMES_HOME = HOME / ".hermes"
PROJECTS_DIR = VAULT / "projects"
AUDIT_DIR = VAULT / "_meta" / "audits"
TODAY = date.today().isoformat()
REPORT_PATH = AUDIT_DIR / f"{TODAY}-project-state-audit.md"
ALLOWED_PROJECT_STATUSES = {"seed", "active", "paused", "complete", "archived"}
FINAL_STATUSES = {"complete", "archived"}
REQUIRED_ACTIVE_FIELDS = ["priority", "objective", "next_action", "success_criteria", "stop_condition", "review_cadence", "external_workspace", "last_meaningful_update"]
PLACEHOLDER_ACTIVE_PATTERNS = {
    "objective": [r"^Advance .+ to a useful, reviewable outcome\.?$"],
    "success_criteria": [r"Minimum useful result documented in the project hub"],
}


def configure(vault: Path, workspace_root: Path) -> None:
    global VAULT, WORKSPACE_ROOT, PROJECTS_DIR, AUDIT_DIR, REPORT_PATH
    VAULT = vault
    WORKSPACE_ROOT = workspace_root
    PROJECTS_DIR = VAULT / "projects"
    AUDIT_DIR = VAULT / "_meta" / "audits"
    REPORT_PATH = AUDIT_DIR / f"{TODAY}-project-state-audit.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(VAULT))
    except Exception:
        return str(path)


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
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
        values = [match.group(2) or ""]
        i += 1
        while i < len(lines) and not key_line.match(lines[i]):
            values.append(lines[i])
            i += 1
        fm[key] = "\n".join(values).strip().strip('"').strip("'")
    return fm


def project_readmes() -> list[Path]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(PROJECTS_DIR.glob("*/README.md"))


def wikilink_slugs(text: str) -> set[str]:
    slugs: set[str] = set()
    for m in re.finditer(r"\[\[projects/([^/\]|#]+)/README", text):
        slugs.add(m.group(1))
    return slugs


def table_rows(text: str) -> list[str]:
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not re.match(r"^\|\s*-", line):
            rows.append(line)
    return rows


def truthy_value(value: str | None) -> bool:
    if value is None:
        return False
    v = value.strip().strip('"').strip("'").lower()
    return bool(v and v not in {"null", "none", "[]", "unknown", "tbd"})


def workspace_for(slug: str, fm: dict[str, str]) -> Path:
    raw = (fm.get("external_workspace") or "").strip()
    if raw and raw.lower() not in {"null", "none", "[]"}:
        return Path(raw).expanduser()
    return WORKSPACE_ROOT / slug


def file_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        return (parse_frontmatter(read(path)).get("status") or "unknown").lower()
    except Exception:
        return "parse-error"


def run_review_scan(vault: Path, workspace_root: Path) -> dict[str, Any]:
    script = HERMES_HOME / "scripts" / "project_review_scan.py"
    if not script.exists():
        return {"error": f"missing scanner {script}"}
    try:
        out = subprocess.check_output([
            "python3", str(script), "--vault", str(vault), "--workspace-root", str(workspace_root), "--dry-run"
        ], text=True, timeout=60)
        return json.loads(out)
    except Exception as exc:
        return {"error": repr(exc)}


def audit() -> dict[str, Any]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    readmes = project_readmes()
    projects: dict[str, dict[str, Any]] = {}
    for path in readmes:
        text = read(path)
        fm = parse_frontmatter(text)
        slug = path.parent.name
        projects[slug] = {"path": path, "text": text, "fm": fm, "status": (fm.get("status") or "unknown").lower()}

    dashboard_path = PROJECTS_DIR / "dashboard.md"
    backlog_path = PROJECTS_DIR / "backlog.md"
    finished_path = PROJECTS_DIR / "finished.md"
    dashboard = read(dashboard_path) if dashboard_path.exists() else ""
    backlog = read(backlog_path) if backlog_path.exists() else ""
    finished = read(finished_path) if finished_path.exists() else ""
    dashboard_slugs = wikilink_slugs(dashboard)
    backlog_slugs = wikilink_slugs(backlog)
    finished_slugs = wikilink_slugs(finished)
    scan = run_review_scan(VAULT, WORKSPACE_ROOT)
    selected = {(item.get("slug"), item.get("mode")) for item in scan.get("ready_projects", []) if isinstance(item, dict)}

    issues: dict[str, list[Any]] = {
        "unsupported_project_status": [],
        "incubating_status": [],
        "dashboard_non_active_rows": [],
        "dashboard_mismatch": [],
        "backlog_missing_seed_or_paused": [],
        "backlog_wrong_status_rows": [],
        "active_missing_required_fields": [],
        "active_placeholder_fields": [],
        "active_workspace_missing": [],
        "active_missing_changelog": [],
        "active_missing_status": [],
        "seed_workspace_or_dashboard_drift": [],
        "seed_missing_activation_or_stop": [],
        "paused_missing_fields": [],
        "finalized_in_active_surfaces": [],
        "finalized_missing_finished_register": [],
        "meaningful_finalized_missing_closeout": [],
        "pending_closeout_not_selected": [],
        "pending_reopen_not_selected": [],
        "web_friction_area_mismatch": [],
        "register_broken_project_links": [],
        "skill_reference_drift": [],
        "workflow_skill_convention_drift": [],
        "scanner_error": [],
    }
    if "error" in scan:
        issues["scanner_error"].append(scan["error"])

    for slug, data in projects.items():
        fm = data["fm"]
        status = data["status"]
        path = data["path"]
        if status not in ALLOWED_PROJECT_STATUSES:
            issues["unsupported_project_status"].append((rel(path), status))
        if status == "incubating" or re.search(r"(?im)^status:\s*incubating\b", data["text"]):
            issues["incubating_status"].append(rel(path))
        if slug == "web-friction-interruptor" and fm.get("area") != "personal":
            issues["web_friction_area_mismatch"].append((rel(path), fm.get("area")))
        if slug in dashboard_slugs and status != "active":
            issues["dashboard_non_active_rows"].append((slug, status))
        if status == "active" and slug not in dashboard_slugs:
            issues["dashboard_mismatch"].append((slug, "active missing from dashboard"))
        if status == "active" and slug in backlog_slugs:
            issues["dashboard_mismatch"].append((slug, "active appears in backlog"))
        if status in {"seed", "paused"} and slug not in backlog_slugs:
            issues["backlog_missing_seed_or_paused"].append((slug, status))
        if slug in backlog_slugs and status not in {"seed", "paused"}:
            issues["backlog_wrong_status_rows"].append((slug, status))
        if status in FINAL_STATUSES and (slug in dashboard_slugs or slug in backlog_slugs):
            issues["finalized_in_active_surfaces"].append((slug, status))
        if status in FINAL_STATUSES and slug not in finished_slugs:
            issues["finalized_missing_finished_register"].append((slug, status))
        if status == "active":
            missing = [key for key in REQUIRED_ACTIVE_FIELDS if not truthy_value(fm.get(key))]
            if missing:
                issues["active_missing_required_fields"].append((slug, missing))
            placeholders = [
                key for key, patterns in PLACEHOLDER_ACTIVE_PATTERNS.items()
                if any(re.search(pattern, fm.get(key, ""), re.IGNORECASE) for pattern in patterns)
            ]
            if placeholders:
                issues["active_placeholder_fields"].append((slug, placeholders))
            ws = workspace_for(slug, fm)
            if not ws.exists():
                issues["active_workspace_missing"].append((slug, str(ws)))
            if not (ws / "PROJECT_CHANGELOG.md").exists():
                issues["active_missing_changelog"].append((slug, str(ws / "PROJECT_CHANGELOG.md")))
            if not (ws / "PROJECT_STATUS.md").exists():
                issues["active_missing_status"].append((slug, str(ws / "PROJECT_STATUS.md")))
            closeout = ws / "PROJECT_CLOSEOUT.md"
            reopen = ws / "PROJECT_REOPEN.md"
            if closeout.exists() and file_status(closeout) == "pending" and (slug, "closeout") not in selected:
                issues["pending_closeout_not_selected"].append((slug, str(closeout)))
            if reopen.exists() and file_status(reopen) == "pending" and (slug, "reopen") not in selected:
                issues["pending_reopen_not_selected"].append((slug, str(reopen)))
        elif status == "seed":
            if truthy_value(fm.get("external_workspace")) or slug in dashboard_slugs:
                issues["seed_workspace_or_dashboard_drift"].append((slug, fm.get("external_workspace")))
            if not truthy_value(fm.get("activation_criteria")) or not truthy_value(fm.get("stop_condition")):
                issues["seed_missing_activation_or_stop"].append(slug)
        elif status == "paused":
            missing = [key for key in ["paused", "pause_reason", "resume_condition"] if not truthy_value(fm.get(key))]
            if "next_review" not in fm:
                missing.append("next_review")
            if missing:
                issues["paused_missing_fields"].append((slug, missing))
        elif status in FINAL_STATUSES:
            closeout = fm.get("closeout", "")
            if truthy_value(closeout):
                match = re.search(r"\[\[([^\]|#]+)", closeout)
                ref = match.group(1) if match else closeout
                closeout_path = VAULT / (ref if ref.endswith(".md") else ref + ".md")
                if not closeout_path.exists():
                    issues["meaningful_finalized_missing_closeout"].append((slug, str(closeout_path)))

    # Register links should point to existing project readmes.
    known_slugs = set(projects)
    for surface_name, slugs in [("dashboard", dashboard_slugs), ("backlog", backlog_slugs), ("finished", finished_slugs)]:
        for slug in sorted(slugs):
            if slug not in known_slugs:
                issues["register_broken_project_links"].append((surface_name, slug))

    # Skill/reference presence and basic convention checks.
    skill_dir = HERMES_HOME / "skills" / "automation-agents" / "projects" / "personal-project-management"
    required_refs = [
        "project-registration.md", "project-activation.md", "project-review.md",
        "project-pausing-and-reopening.md", "project-closing.md",
        "project-workspace-control-files.md", "project-state-audit-contract.md",
    ]
    if not (skill_dir / "SKILL.md").exists():
        issues["skill_reference_drift"].append("missing personal-project-management/SKILL.md")
    else:
        skill_text = read(skill_dir / "SKILL.md")
        for ref in required_refs:
            if f"references/{ref}" not in skill_text and ref not in skill_text:
                issues["skill_reference_drift"].append(f"SKILL.md missing reference mention {ref}")
            if not (skill_dir / "references" / ref).exists():
                issues["skill_reference_drift"].append(f"missing references/{ref}")
        if "_meta/workflows/projects/project-registration-workflow" in skill_text:
            issues["skill_reference_drift"].append("SKILL.md points directly to vault workflows as primary process surface")

    convention_terms = {
        "statuses": ["seed", "active", "paused", "complete", "archived"],
        "surfaces": ["projects/dashboard", "projects/backlog", "projects/finished"],
        "workspace_files": ["PROJECT_STATUS.md", "PROJECT_CHANGELOG.md", "PROJECT_CLOSEOUT.md", "PROJECT_REOPEN.md"],
    }
    for ref in required_refs:
        rpath = skill_dir / "references" / ref
        if not rpath.exists():
            continue
        text = read(rpath)
        if "incubating" in text and "retired" not in text:
            issues["workflow_skill_convention_drift"].append((str(rpath), "mentions incubating without retired context"))
    for wf in [
        "project-registration-workflow.md", "project-activation-workflow.md", "project-review-workflow.md",
        "project-pausing-and-reopening-workflow.md", "project-closing-workflow.md",
    ]:
        wpath = VAULT / "_meta" / "workflows" / "projects" / wf
        if not wpath.exists():
            issues["workflow_skill_convention_drift"].append((rel(wpath), "missing workflow doc"))

    issue_count = sum(len(v) for v in issues.values())
    status_counts = Counter(data["status"] for data in projects.values())
    return {
        "wakeAgent": bool(issue_count),
        "vault": str(VAULT),
        "workspace_root": str(WORKSPACE_ROOT),
        "report_path": str(REPORT_PATH),
        "project_count": len(projects),
        "issue_count": issue_count,
        "issue_counts": {k: len(v) for k, v in issues.items()},
        "status_counts": dict(sorted(status_counts.items())),
        "issues": issues,
        "review_scan_ready_count": scan.get("ready_count"),
        "review_scan_selected": scan.get("selected_projects", []),
    }


def bullet_list(items: list[Any], formatter=str, limit: int = 80) -> str:
    if not items:
        return "- None"
    out = [f"- {formatter(item)}" for item in items[:limit]]
    if len(items) > limit:
        out.append(f"- ... {len(items) - limit} more")
    return "\n".join(out)


def write_report(result: dict[str, Any]) -> None:
    issues = result["issues"]
    lines = [
        "---",
        f"title: Project State Audit — {TODAY}",
        f"created: {TODAY}",
        f"updated: {TODAY}",
        "type: audit",
        "status: active",
        "area: meta",
        "tags: [projects, audit, lifecycle]",
        "---",
        "",
        f"# Project State Audit — {TODAY}",
        "",
        "Report-only deterministic audit. This script does not mutate project records or workspaces.",
        "",
        "## Summary",
        "",
        f"- Project count: {result['project_count']}",
        f"- Issue count: {result['issue_count']}",
        f"- Workspace root: `{result['workspace_root']}`",
        f"- Review-scan ready count: {result.get('review_scan_ready_count')}",
        "",
        "## Status counts",
        "",
        bullet_list(sorted(result["status_counts"].items()), lambda kv: f"`{kv[0]}`: {kv[1]}"),
        "",
        "## Findings",
    ]
    for key, values in issues.items():
        lines.extend(["", f"### {key.replace('_', ' ').title()}", bullet_list(values, repr)])
    lines.extend([
        "",
        "## Policy reminders",
        "",
        "- Dashboard is active-only.",
        "- Backlog is seed/paused only.",
        "- Finished is complete/archived only.",
        "- Active projects require `/home/brayan/projects/<slug>/PROJECT_STATUS.md` and `PROJECT_CHANGELOG.md`.",
        "- This report is an input to patch proposals, not automatic approval to close/archive projects.",
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=str(VAULT))
    parser.add_argument("--workspace-root", default=str(WORKSPACE_ROOT))
    parser.add_argument("--dry-run", action="store_true", help="Report-only; retained for command compatibility")
    parser.add_argument("--json", action="store_true", help="Emit compact JSON only (still writes report)")
    args = parser.parse_args()
    configure(Path(args.vault).expanduser().resolve(), Path(args.workspace_root).expanduser().resolve())
    result = audit()
    write_report(result)
    retention = apply_retention(VAULT, groups={"project_state_audits"})
    compact = {k: v for k, v in result.items() if k != "issues"}
    compact["top_issue_summary"] = {k: c for k, c in result["issue_counts"].items() if c}
    compact["retention"] = retention["groups"]["project_state_audits"]
    if args.json:
        print(json.dumps(compact, ensure_ascii=False))
    else:
        print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
