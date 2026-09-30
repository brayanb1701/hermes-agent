"""Runtime skill locks are not reinstallable personalization assets."""
import importlib.util
from pathlib import Path


def test_skill_locks_are_excluded_from_snapshot(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/sync-brayan-personalization.py"
    spec = importlib.util.spec_from_file_location("personalization_sync_locks", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "skills"
    (source / ".locks").mkdir(parents=True)
    (source / ".locks/ledger.lock").write_text("")
    (source / "SKILL.md").write_text("behavior")
    destination = tmp_path / "snapshot"
    module.copy_tree(source, destination)
    assert (destination / "SKILL.md").read_text() == "behavior"
    assert not (destination / ".locks").exists()
