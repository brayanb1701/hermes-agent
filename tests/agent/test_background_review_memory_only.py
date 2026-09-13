from types import SimpleNamespace

from agent.background_review import _review_tool_whitelist


def test_memory_only_blocks_all_other_tools_even_extra_tools():
    agent = SimpleNamespace(_memory_enabled=True, _user_profile_enabled=True)
    allowed, extras = _review_tool_whitelist(agent, {
        'memory_only': True,
        'extra_tools': ['skill_manage', 'terminal', 'write_file'],
    })
    assert allowed == {'memory'}
    assert extras == set()


def test_memory_only_respects_disabled_memory():
    agent = SimpleNamespace(_memory_enabled=False, _user_profile_enabled=False)
    allowed, extras = _review_tool_whitelist(agent, {'memory_only': True})
    assert allowed == set()
    assert extras == set()
