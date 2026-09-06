---
name: pi-cli
description: Use when spawning or coordinating Pi coding agents.
---

# Pi coding CLI

Check pi --version and pi --help on the execution host. Wrapper/version-manager shims may install/update on invocation; inspect command -v and the launcher before diagnosing drift. Preserve the user's existing subscription provider/model; don't print credentials or silently select a billed API.

For SSH-safe interactive Pi workers and multi-harness coordination, load herdr. Kind and integration installer name are both pi. The official extension lives at ~/.pi/agent/extensions/herdr-agent-state.ts (or PI_CODING_AGENT_DIR/extensions). It reports lifecycle and native session path; it is a no-op outside Herdr. Official in-pane Herdr skill lives at ~/.pi/agent/skills/herdr/SKILL.md.

Execution shapes verified against pi --help:
- Interactive: pi, under an explicitly owned Herdr session/pane.
- Headless: pi -p 'SELF-CONTAINED TASK' --mode json; preserve complete output as JSONL and inspect actual completion events/results.
- Exact resume: pi --session <path-or-id>. Prefer exact path/ID, not shared --continue, when concurrent sessions exist.
- Read-only review: pi --tools read,grep,find,ls -p 'Review only; do not modify files.'
- No-tool smoke: pi --no-tools -p 'Reply exactly OK.'
- Explicit skill loading: pi --skill <file-or-directory>.

Supply exact cwd, objective, ownership/non-goals, required tests and output path. Isolate concurrent writers using worktrees/disjoint scope. Pi's default coding tools include bash/edit/write; choose a restrictive tool allowlist for read-only tasks rather than assuming sandbox/approval behavior matches Codex or Claude.

Verify returned files and run tests independently. Herdr lifecycle settling and Pi's self-report are not acceptance criteria. Native restoration needs the official session reference; restart does not resurrect arbitrary shell processes or guarantee autonomous continuation.
