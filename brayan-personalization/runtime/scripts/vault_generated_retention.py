#!/usr/bin/env python3
"""Bound retention for generated personal-vault review artifacts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_VAULT = Path.home() / "personal_vault"
DEFAULT_KEEP = 5
DATE_NOTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
AUDIT_PATTERNS = {
    "vault_structure_audits": "*-vault-structure-audit.md",
    "project_state_audits": "*-project-state-audit.md",
}
DAILY_WIKILINK_RE = re.compile(r"\[\[(daily/\d{4}-\d{2}-\d{2})(?:\.md)?(?:\|([^\]]+))?\]\]")


def _dated_daily_notes(vault: Path) -> list[Path]:
    daily = vault / "daily"
    if not daily.exists():
        return []
    return sorted(
        (path for path in daily.iterdir() if path.is_file() and DATE_NOTE_RE.fullmatch(path.name)),
        key=lambda path: path.name,
        reverse=True,
    )


def _audit_reports(vault: Path, pattern: str) -> list[Path]:
    audit_dir = vault / "_meta" / "audits"
    if not audit_dir.exists():
        return []
    return sorted(
        (path for path in audit_dir.glob(pattern) if path.is_file()),
        key=lambda path: path.name,
        reverse=True,
    )


def prune_paths(paths: list[Path], keep: int, dry_run: bool = False) -> dict[str, Any]:
    if keep < 0:
        raise ValueError("keep must be non-negative")
    retained = paths[:keep]
    removed = paths[keep:]
    if not dry_run:
        for path in removed:
            path.unlink()
    return {
        "before": len(paths),
        "kept": len(retained),
        "removed": len(removed),
        "retained_paths": [str(path) for path in retained],
        "removed_paths": [str(path) for path in removed],
    }


def rewrite_missing_daily_links(vault: Path, files: list[Path], dry_run: bool = False) -> int:
    """Prevent retained rolling notes from linking to snapshots that aged out."""
    rewritten = 0
    for path in files:
        text = path.read_text(encoding="utf-8")

        def replace(match: re.Match[str]) -> str:
            nonlocal rewritten
            target = match.group(1)
            if (vault / f"{target}.md").exists():
                return match.group(0)
            rewritten += 1
            reference = f"`{target}.md`"
            alias = match.group(2)
            return f"{alias} ({reference})" if alias else reference

        updated = DAILY_WIKILINK_RE.sub(replace, text)
        if updated != text and not dry_run:
            path.write_text(updated, encoding="utf-8")
    return rewritten


def apply_retention(
    vault: Path = DEFAULT_VAULT,
    keep: int = DEFAULT_KEEP,
    groups: set[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    vault = vault.expanduser().resolve()
    selected = groups or {"daily", *AUDIT_PATTERNS}
    unknown = selected - {"daily", *AUDIT_PATTERNS}
    if unknown:
        raise ValueError(f"unknown retention groups: {', '.join(sorted(unknown))}")

    results: dict[str, Any] = {}
    if "daily" in selected:
        results["daily"] = prune_paths(_dated_daily_notes(vault), keep, dry_run)
        retained_daily = [Path(path) for path in results["daily"]["retained_paths"]]
        results["daily"]["rewritten_expired_links"] = rewrite_missing_daily_links(vault, retained_daily, dry_run)
    for group, pattern in AUDIT_PATTERNS.items():
        if group in selected:
            results[group] = prune_paths(_audit_reports(vault, pattern), keep, dry_run)

    return {
        "script": "vault_generated_retention.py",
        "vault": str(vault),
        "keep": keep,
        "dry_run": dry_run,
        "groups": results,
        "removed_total": sum(item["removed"] for item in results.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)
    parser.add_argument(
        "--group",
        action="append",
        choices=["daily", *AUDIT_PATTERNS],
        help="Limit pruning to one or more groups; default is all groups.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = apply_retention(
        Path(args.vault),
        keep=args.keep,
        groups=set(args.group) if args.group else None,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
