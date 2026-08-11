#!/usr/bin/env python3
"""Keep only the newest dated topic-recommendation sets."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_PATH = Path.home() / "personal_vault" / "queries" / "topic-recommendations.md"
ENTRY_RE = re.compile(r"(?m)^## (\d{4}-\d{2}-\d{2}) recommendation set\s*$", re.IGNORECASE)


def prune(path: Path, keep: int = 5, dry_run: bool = False) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    matches = list(ENTRY_RE.finditer(text))
    if len(matches) <= keep:
        return {"path": str(path), "before": len(matches), "kept": len(matches), "removed": 0, "dry_run": dry_run}
    entries: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries.append((match.group(1), text[match.start():end].rstrip()))
    retained_dates = {date for date, _ in sorted(entries, key=lambda item: item[0], reverse=True)[:keep]}
    retained = [(date, block) for date, block in entries if date in retained_dates]
    updated = text[:matches[0].start()].rstrip() + "\n\n" + "\n\n".join(block for _, block in retained) + "\n"
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return {
        "path": str(path),
        "before": len(matches),
        "kept": len(retained),
        "removed": len(matches) - len(retained),
        "retained_dates": [date for date, _ in retained],
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=str(DEFAULT_PATH))
    parser.add_argument("--keep", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.keep < 0:
        raise SystemExit("--keep must be non-negative")
    print(json.dumps(prune(Path(args.path).expanduser().resolve(), args.keep, args.dry_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
