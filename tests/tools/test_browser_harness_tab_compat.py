"""Executing-environment gate for named harness dedicated-tab ownership."""
import importlib.metadata
import pytest
from tools.browser_use_cli import _OWN_TAB_PREAMBLE


@pytest.mark.parametrize('version, name, creates', [
    ('0.1.13', 'label', 0), ('0.1.12', 'label', 1),
    ('9.9.9', 'label', 1), (None, 'label', 1), ('0.1.13', 'default', 1),
])
def test_preamble_preserves_unknown_routes_and_uses_proven_named_ownership(tmp_path, monkeypatch, version, name, creates):
    monkeypatch.setenv('BU_NAME', name)
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    import tempfile
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    def installed(distribution):
        if version is None:
            raise importlib.metadata.PackageNotFoundError(distribution)
        return version
    monkeypatch.setattr(importlib.metadata, 'version', installed)
    calls = []
    namespace = {'cdp': lambda method, **kw: calls.append((method, kw)) or {'targetId': 'new'},
                 'switch_tab': lambda target: calls.append(('switch', target))}
    exec(_OWN_TAB_PREAMBLE, namespace)
    assert sum(method == 'Target.createTarget' for method, _ in calls) == creates
