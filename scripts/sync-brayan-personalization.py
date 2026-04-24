#!/usr/bin/env python3
"""Sync Brayan's local Hermes personalization bundle into this repo.

This intentionally captures configuration/behavior assets that live outside the
Hermes source checkout so Brayan can reinstall Darwin on another machine:
- ~/.hermes/config.yaml
- ~/.hermes/channel_directory.json
- ~/.hermes/cron/jobs.json, normalized to remove volatile run state
- ~/.hermes/agents/
- ~/.hermes/skills/ (excluding hub/cache noise)
- ~/.hermes/plugins/
- ~/.hermes/scripts/ (excluding caches)

It does not copy secrets (.env, auth.json), sessions, logs, state DBs, caches,
checkpoints, OCR model caches, or generated cron output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
BUNDLE = REPO / "brayan-personalization" / "runtime"

COPY_DIRS = ["agents", "skills", "plugins", "scripts"]
COPY_FILES = ["config.yaml", "channel_directory.json"]

SECRET_LITERAL_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
]
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)^\s*([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|AUTHORIZATION)[A-Z0-9_]*)\s*[:=]\s*['\"]?([^'\"#\s][^#]*)"
)

IGNORE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".hub",  # skills hub cache/state, not Brayan-authored behavior
    "output",  # cron outputs
}
IGNORE_FILE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp", ".swp"}
IGNORE_FILE_NAMES = {
    ".tick.lock",
    "auth.json",
    ".env",
    "state.db",
    "state.db-shm",
    "state.db-wal",
    ".skills_prompt_snapshot.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def should_ignore(path: Path) -> bool:
    parts = set(path.parts)
    if parts & IGNORE_DIR_NAMES:
        return True
    if path.name in IGNORE_FILE_NAMES:
        return True
    if path.suffix in IGNORE_FILE_SUFFIXES:
        return True
    return False


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dst: Path) -> int:
    count = 0
    if not src.exists():
        return count
    reset_dir(dst)
    for item in src.rglob("*"):
        if should_ignore(item):
            continue
        rel = item.relative_to(src)
        out = dst / rel
        if item.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, out)
            count += 1
    return count


def normalize_cron_jobs(raw: dict[str, Any]) -> dict[str, Any]:
    normalized_jobs = []
    volatile_null = {
        "last_run_at",
        "last_status",
        "last_error",
        "last_delivery_error",
        "paused_at",
        "paused_reason",
        "origin",
    }
    for job in raw.get("jobs", []):
        keep = dict(job)
        for key in volatile_null:
            keep[key] = None
        if isinstance(keep.get("repeat"), dict):
            keep["repeat"] = {**keep["repeat"], "completed": 0}
        keep["state"] = "scheduled" if keep.get("enabled", True) else "paused"
        keep["next_run_at"] = None
        normalized_jobs.append(keep)
    return {
        "_portable_note": (
            "Portable Brayan/Darwin cron job definitions. Volatile run state was reset by "
            "scripts/sync-brayan-personalization.py. Secrets are not included."
        ),
        "updated_at": utc_now(),
        "jobs": normalized_jobs,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_file(src: Path, dst: Path) -> bool:
    if not src.exists() or should_ignore(src):
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def scan_for_secrets(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or should_ignore(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if "xxx" in stripped.lower() or "..." in stripped:
                continue
            if any(p.search(stripped) for p in SECRET_LITERAL_PATTERNS):
                hits.append(f"{path.relative_to(root)}:{i}: {stripped[:160]}")
    return hits


def sync(hermes_home: Path, *, check_secrets: bool = True) -> dict[str, Any]:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "generated_at": utc_now(),
        "source_hermes_home": str(hermes_home),
        "bundle_root": str(BUNDLE.relative_to(REPO)),
        "copied_dirs": {},
        "copied_files": [],
        "excluded": [
            ".env",
            "auth.json",
            "sessions/",
            "logs/",
            "state.db*",
            "cron/output/",
            "checkpoints/",
            "venvs/",
            "model caches",
        ],
    }

    for name in COPY_DIRS:
        count = copy_tree(hermes_home / name, BUNDLE / name)
        manifest["copied_dirs"][name] = count

    for name in COPY_FILES:
        if copy_file(hermes_home / name, BUNDLE / name):
            manifest["copied_files"].append(name)

    cron_src = hermes_home / "cron" / "jobs.json"
    if cron_src.exists():
        raw = json.loads(cron_src.read_text(encoding="utf-8"))
        write_json(BUNDLE / "cron" / "jobs.json", normalize_cron_jobs(raw))
        manifest["copied_files"].append("cron/jobs.json")

    write_json(BUNDLE / "manifest.json", manifest)

    if check_secrets:
        hits = scan_for_secrets(BUNDLE)
        if hits:
            raise SystemExit("Secret-looking content found in personalization bundle:\n" + "\n".join(hits[:50]))

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-home", default=str(DEFAULT_HERMES_HOME), help="Runtime Hermes home to snapshot")
    parser.add_argument("--no-secret-scan", action="store_true", help="Skip conservative secret scan")
    args = parser.parse_args()

    manifest = sync(Path(args.hermes_home).expanduser(), check_secrets=not args.no_secret_scan)
    print(json.dumps({"ok": True, "manifest": manifest}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
