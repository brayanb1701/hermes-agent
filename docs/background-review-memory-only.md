# Memory-only background review

Local option: `auxiliary.background_review.memory_only: true`.

The detached reviewer receives a memory-only prompt and its dispatch allowlist is
exactly `{memory}` when built-in memory or the user profile is enabled, otherwise
empty. Configured `extra_tools` cannot widen this allowlist. This restriction also
applies to explicit `/refine` review forks; ordinary foreground tools are unchanged.
The default is false for compatibility. No skill/library migration is performed.

Enable with `hermes config set auxiliary.background_review.memory_only true`.
Keep memory enabled and a nonzero memory nudge interval if automatic memory
reviews are desired. Skill nudge interval may remain zero. Curator is independent.

Source changes require restarting/relaunching existing Hermes processes. Merely
resuming a conversation in the same process does not reload this module.
After code activation the option is read for subsequent reviews; already-running
review forks are not retroactively changed.

Verification:
`scripts/run_tests.sh tests/agent/test_background_review_memory_only.py tests/run_agent/test_background_review_toolset_restriction.py`

Rollback: set the option false to restore the prior review permissions, or revert
the scoped source commit. Neither operation removes any previously created skill.
