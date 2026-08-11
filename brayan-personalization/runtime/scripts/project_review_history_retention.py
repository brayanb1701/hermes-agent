#!/usr/bin/env python3
"""Keep bounded dated review history in personal-vault project hubs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_VAULT = Path.home() / "personal_vault"
DEFAULT_KEEP = 5
SECTION_RE = re.compile(r"^## (?:(?:Cadence )?Review notes|Review log)\s*$", re.MULTILINE | re.IGNORECASE)
NEXT_H2_RE = re.compile(r"(?m)^## (?!#)")
HEADING_ENTRY_RE = re.compile(r"(?m)^### (\d{4}-\d{2}-\d{2})\b")
BULLET_ENTRY_RE = re.compile(r"(?m)^- (\d{4}-\d{2}-\d{2})(?::|\s+—)\s*")


def _prune_section(section: str, keep: int) -> tuple[str, int]:
    heading_matches = list(HEADING_ENTRY_RE.finditer(section))
    if heading_matches:
        entries = []
        for index, match in enumerate(heading_matches):
            end = heading_matches[index + 1].start() if index + 1 < len(heading_matches) else len(section)
            entries.append((match.group(1), section[match.start():end]))
        newest = sorted(entries, key=lambda item: item[0], reverse=True)[:keep]
        prefix = section[:heading_matches[0].start()]
        return prefix.rstrip() + "\n\n" + "\n".join(block.rstrip() for _, block in newest) + "\n", max(0, len(entries) - keep)

    lines = section.splitlines(keepends=True)
    dated: list[tuple[str, str]] = []
    undated: list[str] = []
    for line in lines:
        match = BULLET_ENTRY_RE.match(line)
        if match:
            dated.append((match.group(1), line))
        else:
            undated.append(line)
    if not dated:
        return section, 0
    newest = sorted(dated, key=lambda item: item[0], reverse=True)[:keep]
    rebuilt = "".join(undated).rstrip() + "\n" + "".join(line for _, line in newest)
    return rebuilt.rstrip() + "\n", max(0, len(dated) - keep)


def prune_project(path: Path, keep: int = DEFAULT_KEEP, dry_run: bool = False) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    sections = list(SECTION_RE.finditer(text))
    removed = 0
    updated = text
    for match in reversed(sections):
        section_start = match.end()
        next_h2 = NEXT_H2_RE.search(updated, section_start)
        section_end = next_h2.start() if next_h2 else len(updated)
        pruned, count = _prune_section(updated[section_start:section_end], keep)
        updated = updated[:section_start] + pruned + updated[section_end:]
        removed += count
    if removed and not dry_run:
        path.write_text(updated, encoding="utf-8")
    return {"path": str(path), "removed": removed, "changed": bool(removed), "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", help="One projects/<slug>/README.md path")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    parser.add_argument("--all", action="store_true", help="Process all project hubs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.keep < 0:
        raise SystemExit("--keep must be non-negative")
    vault = Path(args.vault).expanduser().resolve()
    if args.all:
        paths = sorted((vault / "projects").glob("*/README.md"))
    elif args.project:
        paths = [Path(args.project).expanduser().resolve()]
    else:
        raise SystemExit("Choose --project PATH or --all")
    results = [prune_project(path, args.keep, args.dry_run) for path in paths]
    print(json.dumps({
        "script": "project_review_history_retention.py",
        "keep": args.keep,
        "removed_total": sum(item["removed"] for item in results),
        "changed_files": [item["path"] for item in results if item["changed"]],
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
