#!/usr/bin/env python3
"""Install Brayan's source-controlled Hermes personalization bundle.

Run from a checkout of brayanb1701/hermes-agent after the base Hermes install.
By default this performs a dry run. Pass --apply to copy files into HERMES_HOME.

Secrets are intentionally not included. After applying, run provider/platform auth
setup locally (for example `hermes login --provider openai-codex` and Telegram
bot token setup if this machine should run the gateway).
"""
from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "brayan-personalization" / "runtime"
DEFAULT_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
COPY_DIRS = ["agents", "skills", "plugins", "scripts"]
COPY_FILES = ["config.yaml", "channel_directory.json"]


def backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(path.name + f".bak-{stamp}")


def copy_dir(src: Path, dst: Path, *, apply: bool, backup: bool) -> None:
    if not src.exists():
        return
    print(f"DIR  {src.relative_to(REPO)} -> {dst}")
    if not apply:
        return
    if dst.exists() and backup:
        b = backup_path(dst)
        print(f"     backup -> {b}")
        shutil.move(str(dst), str(b))
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path, *, apply: bool, backup: bool) -> None:
    if not src.exists():
        return
    print(f"FILE {src.relative_to(REPO)} -> {dst}")
    if not apply:
        return
    if dst.exists() and backup:
        b = backup_path(dst)
        print(f"     backup -> {b}")
        shutil.move(str(dst), str(b))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", default=str(DEFAULT_HERMES_HOME), help="Destination Hermes home")
    parser.add_argument("--apply", action="store_true", help="Actually copy files; default is dry-run")
    parser.add_argument("--no-backup", action="store_true", help="Overwrite without .bak timestamp backups")
    args = parser.parse_args()

    hermes_home = Path(args.hermes_home).expanduser()
    if not BUNDLE.exists():
        raise SystemExit(f"Missing bundle: {BUNDLE}. Run scripts/sync-brayan-personalization.py first.")

    print(f"Bundle: {BUNDLE}")
    print(f"Destination HERMES_HOME: {hermes_home}")
    print("Mode:", "APPLY" if args.apply else "DRY RUN")
    print()

    backup = not args.no_backup
    for name in COPY_DIRS:
        copy_dir(BUNDLE / name, hermes_home / name, apply=args.apply, backup=backup)
    for name in COPY_FILES:
        copy_file(BUNDLE / name, hermes_home / name, apply=args.apply, backup=backup)
    copy_file(BUNDLE / "cron" / "jobs.json", hermes_home / "cron" / "jobs.json", apply=args.apply, backup=backup)

    print()
    if not args.apply:
        print("Dry run only. Re-run with --apply to install the personalization bundle.")
    else:
        print("Applied. Next steps:")
        print("  1. Restore secrets/auth locally: ~/.hermes/.env, hermes login, platform tokens.")
        print("  2. Run: hermes config check")
        print("  3. If using messaging: hermes gateway restart && hermes gateway status")


if __name__ == "__main__":
    main()
