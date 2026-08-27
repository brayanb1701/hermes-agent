---
name: antigravity-cli
description: Use when calling Google Antigravity agents through agy. Run headless, interactive, resumed, structured, or custom-agent workflows safely and verify their work.
version: 0.3.0-local
author: Tony Simons (asimons81), Hermes Agent; updated for agy 1.1.22
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [coding-agent, antigravity, cli, delegation, headless, subagents]
    related_skills: [codex, claude-code, hermes-agent]
---

# Antigravity CLI (`agy`)

Use Google Antigravity as a coding worker, reviewer, research agent, or custom agent through Hermes' `terminal` and `process` tools. Prefer headless JSON mode for automation. Use the TUI only when the user needs a live conversation, approvals, artifact review, or subagent monitoring.

Official docs:

- https://antigravity.google/docs/cli/headless
- https://antigravity.google/docs/cli/subagents
- https://antigravity.google/docs/cli/permissions
- https://antigravity.google/docs/cli/commands/agents
- https://antigravity.google/docs/cli/reference

## When to use

- Delegate a feature, bug fix, test run, code review, or repository analysis to Antigravity.
- Ask for a Gemini-family or Claude second opinion using Antigravity's model catalog.
- Run a custom Antigravity agent with `--agent`.
- Maintain a multi-turn conversation through a conversation ID or NDJSON stdin.
- Install, update, authenticate, configure, or troubleshoot `agy`.

Do not treat `agy` as Hermes' coordination layer. Hermes owns task decomposition, worktree isolation, acceptance criteria, and final verification. Antigravity is a worker.

## Prerequisites

Check the live installation instead of assuming it exists:

```text
terminal(command="command -v agy && agy --version && agy models", timeout=60)
```

Authentication uses Antigravity's OS keyring. If a headless run says authentication is required, start `agy` interactively with `pty=true`, complete Google OAuth, and then retry. Never expose or store OAuth codes in a skill or memory.

Current local paths:

- Binary: `~/.local/bin/agy`, normally available as `agy`
- Settings: `~/.gemini/antigravity-cli/settings.json`
- Keybindings: `~/.gemini/antigravity-cli/keybindings.json`
- Global custom agents: `~/.gemini/config/agents/<name>/agent.md`
- Workspace agents: `.agents/agents/<name>.md` or `.agents/agents/<name>/agent.md`
- Workspace skills: `.agents/skills/*.md`
- Global Antigravity skills: `~/.gemini/antigravity-cli/skills/*.md`
- Logs: `~/.gemini/antigravity-cli/log/cli-*.log`
- Conversations: `~/.gemini/antigravity-cli/conversations/`

Inspect files with `read_file`, not shell output.

## Pick the execution shape

### One-shot headless run

This is the default for Hermes automation. Run inside the target project directory and request JSON:

```text
terminal(
  command="agy -p 'Review the current diff. Report concrete bugs with file and line references. Do not edit files.' --output-format json --print-timeout 10m",
  workdir="/path/to/repo",
  timeout=600
)
```

The JSON envelope contains `conversation_id`, `status`, `response`, `duration_seconds`, `num_turns`, and token `usage`. Parse the envelope and require `status == "SUCCESS"`. A zero shell exit is necessary but not sufficient for task completion.

Use exact model slugs from `agy models`, for example:

```text
agy -p 'Analyze this race condition' --output-format json --model gemini-3.1-pro-high --effort high
agy -p 'Review this design' --output-format json --model claude-opus-4-6-thinking
```

Unknown model slugs fail loudly. Do not hardcode display labels when a slug is available.

### Structured output

Use `--json-schema` when Hermes must consume fields rather than prose. It accepts an inline schema, a schema file, or a primitive type:

```text
terminal(
  command="agy -p 'Review the current diff' --output-format json --json-schema review-schema.json --print-timeout 10m",
  workdir="/path/to/repo",
  timeout=600
)
```

Read the parsed value from `structured_output`. Keep the schema small and require only fields the caller needs.

### Long coding run

Use a tracked background process for work that may exceed the foreground limit:

```text
terminal(
  command="agy -p 'Implement TASK.md, run the focused tests, and report changed files and exact test results.' --output-format json --print-timeout 30m",
  workdir="/path/to/worktree",
  background=true,
  notify_on_complete=true
)
```

Do not poll repeatedly. Continue other work and inspect the process output when completion is reported. For parallel coding tasks, create one git worktree per worker and cap concurrency to the machine and review capacity.

### Resume a prior conversation

Capture `conversation_id` from JSON output, then resume that exact session:

```text
agy -p 'Now address the two review findings and rerun tests.' --conversation <conversation-id> --output-format json
```

`--continue` or `-c` resumes the most recent conversation, which is convenient but unsafe when several agents run concurrently. Prefer `--conversation <id>` in automation.

### Persistent multi-turn process

For several dependent turns without startup overhead, use both stream formats:

```text
agy --input-format stream-json --output-format stream-json
```

Write one NDJSON line per turn:

```json
{"event":"user","message":{"content":"Inspect the parser and list likely bugs."}}
```

Read stdout line by line. Wait for the `result` event before sending the next prompt. Close stdin to end the process cleanly. Do not send CLI slash commands such as `/model` into this stream. The stream supports `user` messages with string content or text blocks only.

The output sequence is one `init`, any number of `step_update` events, and one `result` per turn. Tool steps include `tool_info`; spawned workers include `subagent_info`. This is the best mode for a driver that needs progress, tool-call visibility, or cumulative token usage.

### Interactive TUI

Start a live session only when interactivity matters:

```text
terminal(command="agy", workdir="/path/to/repo", background=true, pty=true, notify_on_complete=true)
```

Use `process(action="write", data="<prompt>\r", session_id=...)` to submit TUI input. A carriage return may work where a newline does not. Useful in-session commands include `/agents`, `/tasks`, `/diff`, `/permissions`, `/model`, `/skills`, `/resume`, and `/exit`.

The `/agents` panel switches custom agents and monitors Antigravity-spawned subagents. It is not the same as the shell command `agy agents`, which only lists available custom agents.

## Custom agents

List discoverable agents:

```text
terminal(command="agy agents", timeout=60)
```

Run one headlessly:

```text
terminal(
  command="agy -p 'Review the current branch against main.' --agent code-reviewer --output-format json --print-timeout 10m",
  workdir="/path/to/repo",
  timeout=600
)
```

A global custom agent lives at `~/.gemini/config/agents/<name>/agent.md`. A workspace agent lives under `.agents/agents/`. Minimal format:

```markdown
---
name: code-reviewer
description: Reviews diffs for correctness, security, and missing tests.
---
You are a rigorous code reviewer. Cite files and lines. Do not edit unless asked.
```

Add `subagent: true` in frontmatter when the primary Antigravity agent should be able to call it through `invoke_subagent`. Agent switches fork conversation history, so do not assume they mutate the existing thread in place.

## Permissions and safety

Headless mode cannot answer approval prompts. By default, workspace file reads and writes are allowed, while shell commands, web actions, MCP calls, and access outside the workspace usually require approval. Approval-required tools are soft-denied in headless mode. The run may still exit `0` and return `SUCCESS`, so inspect the response and verify the requested effects.

Prefer scoped rules in `~/.gemini/antigravity-cli/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "command(git status)",
      "command(npm run (build|lint|test))",
      "write_file(src/)"
    ],
    "deny": [
      "command(sudo)",
      "command(rm -rf)",
      "write_file(.git/)"
    ]
  }
}
```

Use `--sandbox` for terminal containment. Use `--dangerously-skip-permissions` only when the user has authorized autonomous edits and commands, the workspace is isolated or disposable, and the prompt and repository content are trusted. That flag allows all tools, including command execution and file writes.

Never grant broad access merely to make a run pass. If a tool is soft-denied, either add the smallest permission rule, switch to an interactive approval flow, or perform that operation with Hermes tools.

## Prompt contract for delegated work

A strong prompt includes:

1. Goal and target repository.
2. Exact files, issue text, or starting evidence.
3. Allowed edits and explicit non-goals.
4. Required tests or commands.
5. Acceptance criteria.
6. Required final report: changed files, commands run, raw pass/fail results, and blockers.

For implementation, add: "Do not claim success unless you ran the requested tests. If a permission denial blocks a command, report it explicitly."

For review, add: "Do not edit files. Rank findings by severity and cite file paths and line numbers. Return no finding when evidence is insufficient."

## Verification after every worker run

Antigravity's final message is a self-report. Verify independently before telling the user the work is done.

- Parse JSON and require `status == "SUCCESS"`.
- For edits, inspect `git status --short`, `git diff --check`, and the actual diff.
- Run the relevant tests with Hermes' terminal tool. Do not rely only on Antigravity's claim.
- For generated files, check the exact path and exercise the artifact.
- For external writes, read back the target system.
- For reviews, spot-check cited files and lines.
- Preserve the `conversation_id` if a follow-up turn may be needed.

## Troubleshooting

- `agy help` shows shell commands. TUI slash commands exist only inside `agy`.
- `agy --version` is the reliable version probe.
- `agy -p` defaults to plain text. Add `--output-format json` for automation.
- Headless timeout defaults to five minutes. Raise `--print-timeout` and the Hermes terminal timeout together.
- A successful run may have soft-denied tools. Search stderr/response for permission notices and verify side effects.
- `--input-format stream-json` requires `--output-format stream-json`.
- In streaming input, cumulative `usage`, `duration_seconds`, and `num_turns` cover the session; `response` covers only the current turn.
- If `agy agents` prints nothing, no custom agents are installed. The default agent still works.
- Start with the newest `~/.gemini/antigravity-cli/log/cli-*.log` for failures.
- `agy changelog` is useful because the CLI is changing quickly. Re-check `agy --help` and official headless docs before changing this skill.

## Verification checklist

- [ ] `command -v agy` resolves and `agy --version` succeeds.
- [ ] Cached authentication supports a headless run.
- [ ] JSON output parses and reports `SUCCESS`.
- [ ] The requested model or custom agent was selected explicitly when needed.
- [ ] Permission scope matches the task.
- [ ] The target workspace or worktree is correct.
- [ ] File changes and tests were independently verified.
- [ ] The final report includes the exact executed result, not a plausible summary.
