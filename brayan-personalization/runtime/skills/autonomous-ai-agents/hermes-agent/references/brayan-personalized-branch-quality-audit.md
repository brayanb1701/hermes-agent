# Brayan personalized branch quality-audit pattern

Use when Brayan asks whether his Hermes personalization/fork is causing degraded responses.

## Baseline/update sequence

1. Start read-only and identify the branch layout:
   - `git status --short --branch`
   - `git remote -v`
   - `git log --oneline --decorate -12`
2. Fetch official and fork refs:
   - `git fetch upstream main --prune`
   - `git fetch origin main brayan/personal-hermes-customizations --prune`
3. Update `main` as the clean baseline:
   - `git switch main`
   - `git rebase upstream/main`
   - resolve conflicts preserving upstream framework fixes and Brayan-specific hooks/extensions
   - after conflict resolution: `git add ... && GIT_EDITOR=true git rebase --continue`
4. Verify updated baseline using repo venv, not the system Python:
   - `.venv/bin/python -m py_compile <touched files>`
   - `.venv/bin/python -m pytest <focused tests> -q -o 'addopts='`
   - `python -m pytest` may fail because system Python may not have pytest.
5. Switch back to the original/personalized branch unless the user explicitly asked to leave the checkout elsewhere.

## Comparison commands

```bash
git rev-list --left-right --count brayan/personal-hermes-customizations...main
git log --oneline --decorate --left-only --cherry-pick --no-merges brayan/personal-hermes-customizations...main
git log --oneline --decorate --right-only --cherry-pick --no-merges brayan/personal-hermes-customizations...main
git diff --stat main..brayan/personal-hermes-customizations
git diff --name-status main..brayan/personal-hermes-customizations
```

Filter out expected personalization-bundle noise separately:

```bash
git diff --name-status $(git merge-base main brayan/personal-hermes-customizations)..brayan/personal-hermes-customizations \
  | grep -v '^A[[:space:]]*brayan-personalization/runtime/skills/' \
  | grep -v '^A[[:space:]]*brayan-personalization/runtime/'
```

## Regression suspects to inspect

Prioritize these when responses/tool use feel degraded:

- `run_agent.py`: concurrent tool execution should propagate ContextVars with `contextvars.copy_context()` and `executor.submit(ctx.run, ...)`.
- `run_agent.py` and `agent/transports/chat_completions.py`: thinking providers need `reasoning_content` preserved from direct attributes and `model_extra`; DeepSeek/Kimi/Moonshot may need empty-string padding on assistant tool-call messages.
- `agent/auxiliary_client.py`: keep raw `base_url` for transport detection even when normalizing OpenAI-compatible paths such as Kimi `/coding/v1`.
- `gateway/run.py`: merge Brayan Anything Inbox enrichment with upstream native image-routing rather than replacing one with the other.
- `tools/skill_usage.py`, `agent/curator.py`, `hermes_cli/curator.py`: curator should consider latest activity across use/view/patch and restore nested archive dirs.
- TUI/CLI terminal handling: stale branches may miss mouse/terminal-mode leak fixes and max-turn config fixes.
- Config/persona: check `_config_version`, `agent.system_prompt`, `prefill_messages_file`, `SOUL.md`, active model/provider, reasoning effort, tool progress, interim messages, and display markdown settings.
- Risky skill corpus entries: jailbreak/red-team skills that can write `agent.system_prompt` or prefill files are not necessarily active, but verify they have not modified live config.

## Report structure

Keep the user-facing report concrete:

- What was updated and verified.
- Current branch state and whether anything was pushed.
- Counts: personal-only commits, main-only commits, broad diff size.
- Findings ranked by likely impact, with file/commit evidence.
- Distinguish actual corruption from perceived-quality settings/noise.
- Recommended next actions: rebase personalization branch, targeted tests, config migration, prompt/skill bloat reduction, and risky-skill quarantine if warranted.
