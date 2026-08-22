#!/usr/bin/env python3
"""Wake-gate for Darwin's inbox triage cron.

This script is intentionally deterministic and cheap. It scans
~/personal-vault/inbox for actionable transient items. If the inbox contains
only README.md / hidden-noise files, it emits {"wakeAgent": false} so Hermes
cron skips the LLM call. If actionable items exist, it emits compact JSON for
the cron agent to use as context.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_VAULT = Path(os.environ.get("PERSONAL_VAULT", "~/personal-vault")).expanduser()
INBOX_DIR = DEFAULT_VAULT / "inbox"
PROMPT_TEMPLATE = Path("~/.hermes/agents/inbox-triage/prompt-template.md").expanduser()

IGNORED_NAMES = {
    "README.md",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    ".gitkeep",
}
IGNORED_SUFFIXES = {".tmp", ".swp", ".part", ".crdownload"}


def _is_noise(path: Path) -> bool:
    name = path.name
    if name in IGNORED_NAMES:
        return True
    if name.startswith("."):
        return True
    if path.suffix.lower() in IGNORED_SUFFIXES:
        return True
    return False


def _iter_actionable_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), key=lambda p: str(p.relative_to(root)).lower()):
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part.startswith(".") for part in rel_parts):
            continue
        if _is_noise(path):
            continue
        if path.is_file():
            yield path


def _iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return None


def _top_level_items(root: Path) -> list[dict]:
    if not root.exists():
        return []

    actionable_files = list(_iter_actionable_files(root))
    by_top: dict[str, list[Path]] = {}
    for file_path in actionable_files:
        rel = file_path.relative_to(root)
        top = rel.parts[0]
        by_top.setdefault(top, []).append(file_path)

    items: list[dict] = []
    for top_name, files in sorted(by_top.items(), key=lambda kv: kv[0].lower()):
        top_path = root / top_name
        if top_path.is_file():
            try:
                size = top_path.stat().st_size
            except OSError:
                size = None
            items.append(
                {
                    "relative_path": top_name,
                    "path": str(top_path),
                    "type": "file",
                    "size_bytes": size,
                    "modified_utc": _iso_mtime(top_path),
                }
            )
        else:
            total_size = 0
            for p in files:
                try:
                    total_size += p.stat().st_size
                except OSError:
                    pass
            items.append(
                {
                    "relative_path": top_name,
                    "path": str(top_path),
                    "type": "directory",
                    "child_file_count": len(files),
                    "total_child_size_bytes": total_size,
                    "sample_children": [str(p.relative_to(root)) for p in files[:10]],
                    "modified_utc": _iso_mtime(top_path),
                }
            )
    return items


def build_payload(root: Path) -> dict:
    exists = root.exists()
    items = _top_level_items(root)
    wake = bool(items)
    payload = {
        "wakeAgent": wake,
        "ready_count": len(items),
        "inbox_dir": str(root),
        "inbox_exists": exists,
        "ignored_policy": "README.md, hidden files/dirs, and temporary partial-download/editor files are not actionable inbox work.",
        "prompt_template_path": str(PROMPT_TEMPLATE),
        "agent_skill": "inbox-triage-agent",
        "vault_skill": "personal-vault-ops",
        "items": items,
    }
    if wake:
        payload["instruction"] = (
            "Actionable inbox items exist. Wake the inbox triage agent to inspect these files, "
            "preserve raw source material when relevant, route content into the appropriate durable "
            "vault locations, and remove transient inbox duplicates only after verifying they are safely preserved/routed."
        )
    else:
        payload["reason"] = "No actionable inbox items found. Skip the agent run."
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", default=str(INBOX_DIR), help="Inbox directory to scan")
    parser.add_argument("--quiet-if-empty", action="store_true", help="Emit no stdout when no actionable items exist")
    args = parser.parse_args()

    root = Path(args.inbox).expanduser().resolve()
    payload = build_payload(root)
    if args.quiet_if_empty and not payload["wakeAgent"]:
        return 0
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
