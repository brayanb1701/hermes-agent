#!/usr/bin/env python3
"""Deterministic Vault v2 structure audit.

Report-only / patch-proposal support script. It inventories the personal vault,
flags structural drift, writes a Markdown audit report under _meta/audits/, and
emits compact JSON for a Hermes cron/agent to summarize.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HOME = Path.home()
VAULT = HOME / "personal_vault"
AUDIT_DIR = VAULT / "_meta" / "audits"
TODAY = date.today().isoformat()
REPORT_PATH = AUDIT_DIR / f"{TODAY}-vault-structure-audit.md"

ALLOWED_TYPES = {
    "raw-source", "concept", "principle", "reference", "project", "opportunity-record",
    "application-packet", "application-draft", "profile", "workflow", "guide", "architecture",
    "domain", "query", "decision-register", "daily", "template", "index", "audit", "comparison",
}
ALLOWED_STATUSES = {
    "seed", "active", "pending", "reference", "captured", "researched", "tailoring-ready",
    "awaiting-review", "draft", "submitted", "applied", "paused", "archived", "complete",
}
OPPORTUNITY_STATUSES = {"captured", "researched", "tailoring-ready", "awaiting-review", "applied", "archived"}
ALLOWED_AREAS = {"ai", "physics", "coding", "creative", "economy", "opportunities", "meta", "personal", "other"}
OLD_PATH_PATTERNS = [
    "projects/job-opportunities",
    "projects/job-application-packets",
    "projects/job-application-cv-master",
    "projects/project-backlog",
    "projects/pending-decisions",
    "inbox/inbox.md",
    "inbox/idea-garden.md",
    "inbox/_captures",
]
IGNORE_OLD_PATH_IN = {
    "_meta/log.md",
}
IGNORE_PREFIXES = (
    "_meta/migration_v2_vault/",
    "_meta/audits/",
)


def rel(path: Path) -> str:
    return str(path.relative_to(VAULT))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith(" ") or line.startswith("-") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def all_notes() -> list[Path]:
    return sorted(p for p in VAULT.rglob("*.md") if ".git" not in p.parts)


def build_note_index(notes: list[Path]) -> tuple[set[str], dict[str, list[str]]]:
    paths = {rel(p)[:-3] for p in notes}
    by_stem: dict[str, list[str]] = defaultdict(list)
    for p in notes:
        by_stem[p.stem].append(rel(p)[:-3])
    return paths, by_stem


def resolve_wikilink(target: str, paths: set[str], by_stem: dict[str, list[str]]) -> bool:
    target = target.split("#", 1)[0].split("|", 1)[0].strip()
    if not target:
        return True
    if "{{" in target or "}}" in target or "<" in target or ">" in target:
        return True
    raw_target = target
    target = target[:-3] if target.endswith(".md") else target
    if target in paths:
        return True
    if target.startswith("/") and target[1:] in paths:
        return True
    if target in by_stem:
        return True
    # Obsidian can link non-Markdown assets or folders; resolve those against the vault.
    if (VAULT / raw_target).exists() or (VAULT / target).exists():
        return True
    return False


def git_status() -> str:
    try:
        return subprocess.check_output(["git", "status", "--short", "--branch"], cwd=VAULT, text=True, timeout=20)
    except Exception as exc:
        return f"git status unavailable: {exc!r}"


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    notes = all_notes()
    paths, by_stem = build_note_index(notes)

    counts_by_top = Counter(p.relative_to(VAULT).parts[0] for p in notes)
    counts_by_type = Counter()
    counts_by_status = Counter()
    unsupported = []
    missing_frontmatter = []
    wrong_project_files = []
    project_missing_next = []
    old_path_refs = []
    broken_links = []
    opportunity_issues = []
    reference_queue_issues = []
    semantic_location_issues = []
    old_paths_existing = []

    for p in notes:
        r = rel(p)
        text = read(p)
        fm = parse_frontmatter(text)
        if not fm and not r.startswith("_meta/migration_v2_vault/") and not r.startswith("raw/assets/"):
            missing_frontmatter.append(r)
        typ = fm.get("type", "")
        status = fm.get("status", "")
        area = fm.get("area", "")
        if typ:
            counts_by_type[typ] += 1
            if typ not in ALLOWED_TYPES:
                unsupported.append((r, "type", typ))
        if status:
            counts_by_status[status] += 1
            if status not in ALLOWED_STATUSES:
                unsupported.append((r, "status", status))
        if area and area not in ALLOWED_AREAS:
            unsupported.append((r, "area", area))

        top = Path(r).parts[0] if Path(r).parts else ""
        if r == "inbox/README.md":
            pass
        elif top == "inbox":
            semantic_location_issues.append((r, "inbox/ should contain only transient manual files; durable captures belong under raw/ and this should be manually triaged"))
        elif top == "references" and r != "references/README.md" and typ != "reference":
            semantic_location_issues.append((r, "references/ notes should use type: reference"))
        elif top == "references" and r != "references/README.md" and status != "reference":
            semantic_location_issues.append((r, "references/ notes should use status: reference"))
        elif top == "concepts" and (typ == "reference" or status == "reference"):
            semantic_location_issues.append((r, "passive references should live under references/, not concepts/"))
        elif top == "concepts" and re.search(r"tool|tools|tooling|cookbook|resource", p.stem, re.I) and re.search(r"implementation cookbook|tool candidates|use when|candidate list", text, re.I):
            semantic_location_issues.append((r, "tool/resource catalogs should usually live under references/tools/ unless they are conceptual synthesis"))
        elif top == "queries" and typ != "query":
            semantic_location_issues.append((r, "queries/ notes should use type: query"))
        elif top == "domains" and typ != "domain":
            semantic_location_issues.append((r, "domains/ notes should use type: domain"))
        elif top == "decisions" and typ != "decision-register":
            semantic_location_issues.append((r, "decisions/ notes should use type: decision-register"))
        elif top == "profile" and typ != "profile":
            semantic_location_issues.append((r, "profile/ notes should use type: profile"))
        elif top == "raw" and not r.startswith("raw/assets/") and typ and typ != "raw-source":
            semantic_location_issues.append((r, "raw/ notes should preserve source material with type: raw-source"))

        if r.startswith("projects/") and r != "projects/README.md":
            parts = Path(r).parts
            if len(parts) != 3 or parts[-1] != "README.md" or typ != "project":
                wrong_project_files.append(r)
            if typ == "project" and not re.search(r"next action|next_action|next actions", text, re.I):
                project_missing_next.append(r)

        if not r in IGNORE_OLD_PATH_IN and not r.startswith(IGNORE_PREFIXES):
            for pattern in OLD_PATH_PATTERNS:
                if pattern in text:
                    old_path_refs.append((r, pattern))

        if not r.startswith("raw/assets/") and not r.startswith(IGNORE_PREFIXES):
            for m in re.finditer(r"\[\[([^\]]+)\]\]", text):
                target = m.group(1)
                if not resolve_wikilink(target, paths, by_stem):
                    broken_links.append((r, target))

        if r.startswith("queries/") and "awesome-llm-apps" in text:
            if re.search(r"awesome-llm-apps.*\|\s*P[01]\s*\|\s*pending", text, re.I):
                reference_queue_issues.append((r, "awesome-llm-apps appears active pending instead of reference"))

    # Opportunity checks
    for opp in sorted((VAULT / "opportunities").glob("*/opportunity.md")):
        text = read(opp)
        fm = parse_frontmatter(text)
        slug = opp.parent.name
        if fm.get("type") != "opportunity-record":
            opportunity_issues.append((rel(opp), "type is not opportunity-record"))
        if fm.get("status") not in OPPORTUNITY_STATUSES:
            opportunity_issues.append((rel(opp), f"unsupported opportunity status: {fm.get('status')!r}"))
        packet_ref = fm.get("tailoring_packet", "").strip()
        packet = opp.parent / "application" / "tailoring-packet.md"
        if fm.get("status") == "tailoring-ready" and packet.exists():
            opportunity_issues.append((rel(opp), "status tailoring-ready but application/tailoring-packet.md already exists"))
        if packet_ref and packet_ref.lower() not in {"null", "none"}:
            if "tailoring-packet" not in packet_ref:
                opportunity_issues.append((rel(opp), "tailoring_packet does not point to tailoring-packet"))
            elif not packet.exists():
                opportunity_issues.append((rel(opp), "tailoring_packet is set but application/tailoring-packet.md is missing"))

    for pattern in OLD_PATH_PATTERNS:
        candidate = VAULT / pattern
        if candidate.exists():
            old_paths_existing.append(pattern)

    issues = {
        "unsupported_frontmatter": unsupported,
        "missing_frontmatter": missing_frontmatter,
        "wrong_project_files": wrong_project_files,
        "project_missing_next_action": project_missing_next,
        "old_path_references": old_path_refs,
        "broken_wikilinks": broken_links,
        "opportunity_issues": opportunity_issues,
        "reference_queue_issues": reference_queue_issues,
        "semantic_location_issues": semantic_location_issues,
        "old_paths_existing": old_paths_existing,
    }
    issue_count = sum(len(v) for v in issues.values())

    def bullet_list(items, formatter=str, limit=50) -> str:
        if not items:
            return "- None"
        shown = items[:limit]
        lines = [f"- {formatter(item)}" for item in shown]
        if len(items) > limit:
            lines.append(f"- ... {len(items) - limit} more")
        return "\n".join(lines)

    report = f"""---
title: Vault Structure Audit — {TODAY}
created: {TODAY}
updated: {TODAY}
type: audit
status: active
area: meta
tags: [vault, audit, structure, vault-v2]
---

# Vault Structure Audit — {TODAY}

Report-only deterministic audit. This script proposes fixes but does not move/delete/archive notes.

## Summary

- Markdown notes: {len(notes)}
- Issue count: {issue_count}
- Report path: `{rel(REPORT_PATH)}`

## Counts by top-level folder

{bullet_list(sorted(counts_by_top.items()), lambda kv: f"`{kv[0]}`: {kv[1]}")}

## Counts by type

{bullet_list(sorted(counts_by_type.items()), lambda kv: f"`{kv[0]}`: {kv[1]}")}

## Counts by status

{bullet_list(sorted(counts_by_status.items()), lambda kv: f"`{kv[0]}`: {kv[1]}")}

## Findings

### Unsupported frontmatter
{bullet_list(unsupported, lambda x: f"`{x[0]}` has unsupported {x[1]} `{x[2]}`")}

### Missing frontmatter
{bullet_list(missing_frontmatter, lambda x: f"`{x}`")}

### Wrong project-folder files
{bullet_list(wrong_project_files, lambda x: f"`{x}`")}

### Project notes missing next action wording
{bullet_list(project_missing_next, lambda x: f"`{x}`")}

### Old path references in active docs
{bullet_list(old_path_refs, lambda x: f"`{x[0]}` references `{x[1]}`")}

### Broken wikilinks
{bullet_list(broken_links, lambda x: f"`{x[0]}` -> `[[{x[1]}]]`")}

### Opportunity consistency issues
{bullet_list(opportunity_issues, lambda x: f"`{x[0]}` — {x[1]}")}

### Reference-vs-query issues
{bullet_list(reference_queue_issues, lambda x: f"`{x[0]}` — {x[1]}")}

### Semantic location issues
{bullet_list(semantic_location_issues, lambda x: f"`{x[0]}` — {x[1]}")}

### Retired paths still existing on disk
{bullet_list(old_paths_existing, lambda x: f"`{x}`")}

## Patch proposal policy

A follow-up agent may propose exact patches for these findings, but must not delete raw material, archive active P0/P1 work, rewrite application materials, or move large groups of files without Brayan approval.

## Git status at audit time

```text
{git_status().strip()}
```
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps({
        "wakeAgent": bool(issue_count),
        "vault": str(VAULT),
        "report_path": str(REPORT_PATH),
        "note_count": len(notes),
        "issue_count": issue_count,
        "issue_counts": {k: len(v) for k, v in issues.items()},
        "top_level_counts": dict(sorted(counts_by_top.items())),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
