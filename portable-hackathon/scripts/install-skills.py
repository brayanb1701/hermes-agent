#!/usr/bin/env python3
"""Install the curated portable skill set into a Hermes profile.

Dry-run by default. Existing skills with the same names are backed up before
replacement. Use a fresh Hermes profile if these should be the only local
skills in that profile.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="perform the installation")
    parser.add_argument(
        "--hermes-home",
        type=Path,
        default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")),
        help="target Hermes profile root (default: HERMES_HOME or ~/.hermes)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script = Path(__file__).resolve()
    bundle = script.parent.parent
    repo = bundle.parent
    manifest_path = bundle / "skills-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    skills = manifest["skills"]

    names = [entry["name"] for entry in skills]
    if len(skills) != 28 or len(set(names)) != 28:
        raise SystemExit("manifest invariant failed: expected 28 unique skills")

    target_root = args.hermes_home.expanduser().resolve() / "skills" / "hackathon-portable"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = args.hermes_home.expanduser().resolve() / "backups" / f"hackathon-portable-{stamp}"

    plan = []
    for entry in skills:
        source = (repo / entry["source"]).resolve()
        destination = target_root / entry["tier"] / entry["name"]
        if not (source / "SKILL.md").is_file():
            raise SystemExit(f"missing source SKILL.md: {source}")
        plan.append((entry, source, destination))

    print(json.dumps({
        "apply": args.apply,
        "hermes_home": str(args.hermes_home.expanduser().resolve()),
        "target_root": str(target_root),
        "skill_count": len(plan),
        "skills": names,
    }, indent=2))

    if not args.apply:
        return 0

    for entry, source, destination in plan:
        if destination.exists():
            backup = backup_root / entry["tier"] / entry["name"]
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(backup))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)

    installed = list(target_root.rglob("SKILL.md"))
    if len(installed) != 28:
        raise SystemExit(f"post-install invariant failed: found {len(installed)} SKILL.md files")
    print(f"installed 28 curated skills under {target_root}")
    if backup_root.exists():
        print(f"replaced versions backed up under {backup_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
