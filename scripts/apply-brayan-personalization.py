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
import sys
import os
import json
import yaml
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "brayan-personalization" / "runtime"
sys.path.insert(0, str(BUNDLE / "scripts"))
from vault_ownership_common import load_contract
from vault_job_policy import reconcile, export_jobs
DEFAULT_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
COPY_DIRS = ["agents", "skills", "plugins", "scripts"]
COPY_FILES = ["config.yaml", "SOUL.md", "channel_directory.json"]


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
        shutil.copytree(dst, b)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


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
    parser.add_argument(
        "--preserve-config",
        action="store_true",
        help="Do not replace config.yaml (recommended when setup/auth already ran)",
    )
    args = parser.parse_args()

    hermes_home = Path(args.hermes_home).expanduser()
    contract = load_contract(hermes_home)
    if not BUNDLE.exists():
        raise SystemExit(f"Missing bundle: {BUNDLE}. Run scripts/sync-brayan-personalization.py first.")

    print(f"Bundle: {BUNDLE}")
    print(f"Destination HERMES_HOME: {hermes_home}")
    print("Mode:", "APPLY" if args.apply else "DRY RUN")
    print()

    def read_jobs(path):
        return json.loads(path.read_text()) if path.exists() else {"jobs": []}
    cron_path = hermes_home / 'cron' / 'jobs.json'
    original_path = Path(contract['state_dir']) / 'jobs-original.json'
    planned, originals = reconcile(contract, read_jobs(BUNDLE / 'cron' / 'jobs.json'),
                                    read_jobs(cron_path), read_jobs(original_path))
    config_path = hermes_home / 'config.yaml'
    config_source = config_path if args.preserve_config and config_path.exists() else BUNDLE / 'config.yaml'
    config = yaml.safe_load(config_source.read_text()) if config_source.exists() else {}
    config.setdefault('notes_intake', {})['enabled'] = contract['role'] == 'owner'
    config.setdefault('updates', {})['branch'] = contract['maintenance_branch']
    print('Ownership jobs:', [(j['id'], j.get('enabled'), j.get('script')) for j in planned['jobs']])
    print('Native notes intake:', config['notes_intake']['enabled'])
    backup = not args.no_backup
    for name in COPY_DIRS:
        copy_dir(BUNDLE / name, hermes_home / name, apply=args.apply, backup=backup)
    for name in COPY_FILES:
        if name == "config.yaml":
            print(f"SKIP {hermes_home / name} (preserving existing setup/auth config)")
            continue
        copy_file(BUNDLE / name, hermes_home / name, apply=args.apply, backup=backup)
    if args.apply:
        from uuid import uuid4
        def save(path, text):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and backup:
                shutil.copy2(path, backup_path(path))
            temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
            temporary.write_text(text)
            temporary.replace(path)
        # Persist originals BEFORE any wrapper can become runnable. Quiescing
        # the scheduler/gateway is a deployment precondition, not an online upgrade.
        save(original_path, json.dumps(originals, indent=2) + '\n')
        for job in planned['jobs']:
            if job.get('ownership_managed'):
                Path(job['workdir']).mkdir(parents=True, exist_ok=True)
        save(config_path, yaml.safe_dump(config, sort_keys=False))
        save(cron_path, json.dumps(planned, indent=2) + '\n')

    print()
    if not args.apply:
        print("Dry run only. Re-run with --apply to install the personalization bundle.")
    else:
        print("Applied. Next steps:")
        print("  1. Restore/check secrets and auth locally: ~/.hermes/.env, hermes login, platform tokens.")
        print("  2. Run: hermes config check")
        print("  3. If using messaging: hermes gateway restart && hermes gateway status")


if __name__ == "__main__":
    main()
