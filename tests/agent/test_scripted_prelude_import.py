"""The scripted prelude must load on every supported Python runtime."""


def test_scripted_prelude_imports_on_supported_python():
    import importlib

    module = importlib.import_module("agent.turn_scripted_prelude")
    assert module.play_prelude(None, None, None) == ("run", None)
