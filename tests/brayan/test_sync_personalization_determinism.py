"""Determinism regressions for the personalization snapshotter."""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/sync-brayan-personalization.py"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("brayan_personalization_sync", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cron_normalization_drops_snapshot_time():
    sync = load_sync_module()
    raw = {
        "updated_at": "2026-08-10T00:00:00Z",
        "jobs": [{"id": "job", "name": "demo", "last_run_at": "volatile"}],
    }

    first = sync.normalize_cron_jobs(raw)
    raw["updated_at"] = "2026-08-11T00:00:00Z"
    second = sync.normalize_cron_jobs(raw)

    assert first == second
    assert "updated_at" not in first


def test_channel_directory_normalization_drops_rebuild_time():
    sync = load_sync_module()
    raw = {
        "updated_at": "2026-08-10T00:00:00Z",
        "platforms": {"telegram": [{"id": "home", "name": "Anything Inbox"}]},
    }

    normalized = sync.normalize_channel_directory(raw)

    assert normalized == {"platforms": raw["platforms"]}


def test_manifest_does_not_change_only_because_time_passes(tmp_path, monkeypatch):
    sync = load_sync_module()
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    (hermes_home / "SOUL.md").write_text("Darwin", encoding="utf-8")
    repo = tmp_path / "repo"
    bundle = repo / "brayan-personalization/runtime"
    monkeypatch.setattr(sync, "REPO", repo)
    monkeypatch.setattr(sync, "BUNDLE", bundle)

    first = sync.sync(hermes_home)
    second = sync.sync(hermes_home)

    assert first == second
    assert "generated_at" not in first
