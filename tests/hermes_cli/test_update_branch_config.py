"""Regression tests for Brayan's fork update branch default."""

from types import SimpleNamespace
from unittest.mock import patch


def test_update_branch_uses_config_when_cli_flag_is_absent():
    from hermes_cli.main import _resolve_update_branch

    args = SimpleNamespace(branch=None)
    with patch(
        "hermes_cli.config.load_config",
        return_value={"updates": {"branch": "brayan/personal-hermes-customizations"}},
    ):
        assert _resolve_update_branch(args) == "brayan/personal-hermes-customizations"


def test_update_branch_cli_flag_overrides_config():
    from hermes_cli.main import _resolve_update_branch

    args = SimpleNamespace(branch="release-candidate")
    with patch(
        "hermes_cli.config.load_config",
        return_value={"updates": {"branch": "brayan/personal-hermes-customizations"}},
    ):
        assert _resolve_update_branch(args) == "release-candidate"


def test_update_branch_falls_back_to_main_without_config():
    from hermes_cli.main import _resolve_update_branch

    args = SimpleNamespace(branch=None)
    with patch("hermes_cli.config.load_config", return_value={}):
        assert _resolve_update_branch(args) == "main"


def test_update_branch_is_a_recognized_optional_config_key():
    from hermes_cli.config_defaults import DEFAULT_CONFIG

    assert "branch" in DEFAULT_CONFIG["updates"]
    assert DEFAULT_CONFIG["updates"]["branch"] is None
