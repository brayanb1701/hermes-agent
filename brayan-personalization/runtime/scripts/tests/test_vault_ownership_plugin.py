"""Test the actual Hermes hook directives, not a prompt-only policy."""
import importlib.util
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / 'plugins/vault-ownership/__init__.py'


def load():
    assert PLUGIN.exists(), 'ownership plugin is missing'
    spec = importlib.util.spec_from_file_location('ownership_guard_test', PLUGIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_mutations_block_but_worktree_mutations_pass(tmp_path):
    plugin = load()
    vault = tmp_path / 'vault'
    vault.mkdir()
    spec = {'role': 'owner', 'vault_path': str(vault), 'repo_path': str(vault),
            'snapshot_root': str(tmp_path / 'snapshots'), 'state_dir': str(tmp_path / 'state')}
    plugin.get_contract = lambda: spec
    assert plugin.guard_tool('write_file', {'path': str(vault / 'note.md')})['action'] == 'block'
    assert plugin.guard_tool('write_file', {'path': str(tmp_path / 'task' / 'note.md')}) is None
    assert plugin.guard_tool('patch', {'mode': 'patch', 'patch': f'*** Update File: {vault}/note.md'})['action'] == 'block'


def test_terminal_direct_canonical_write_is_blocked(tmp_path):
    plugin = load()
    plugin.get_contract = lambda: dict(role='owner', vault_path=str(tmp_path/'vault'), repo_path=str(tmp_path/'vault'), snapshot_root=str(tmp_path/'snapshots'))
    result = plugin.guard_tool('terminal', {'command': f'python3 mutate.py {tmp_path}/vault'})
    assert result and result['action'] == 'block'


def test_pre_dispatch_preserves_native_authorization_and_media():
    plugin = load()
    assert plugin.pre_dispatch(event=None) is None


def test_invalid_contract_cannot_fail_open(tmp_path):
    plugin = load()
    def invalid():
        raise ValueError('wrong hostname')
    plugin.get_contract = invalid
    assert plugin.guard_tool('write_file', {'path': str(tmp_path / 'anything')})['action'] == 'block'
    assert plugin.pre_dispatch(event=None) is None
