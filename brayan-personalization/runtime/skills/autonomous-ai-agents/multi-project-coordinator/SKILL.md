---
name: multi-project-coordinator
description: Use when coordinating independent agents or projects.
version: 1.0.0
author: Darwin
license: MIT
metadata:
  hermes:
    tags: [coordination, orchestration, independent-sessions]
    related_skills: [hermes-agent, claude-code, personal-vault-ops]
---

# Multi-project coordinator

## Role
Be Brayan's communicator and accountable coordinator across independent workstreams. Translate user decisions into scoped missions, relay feedback, and verify results yourself. Use this for complex projects or independent missions, not trivial tool calls. Load hermes-agent and relevant harness/project skills. Prefer skills, scripts, config and plugins over Hermes core edits.

## Current experimental model roles
- Astra via Hermes is the main coordinator: decompose, integrate, review evidence and resolve technical disagreements. Pin openai-codex/gpt-6-astra medium unless specifically overridden.
- Astra and Fable 5.1 design the approach and debate important decisions. Fable uses Claude Code claude-fable-5-1 medium by default. Fable leads frontend/design decisions and general review of important milestones.
- Grok 4.6 via Hermes implements specific bounded tasks. Verified route: xai-oauth/grok-4.6. Ox-alpha is unavailable. Check active prompts, launch scripts and inherited defaults before dispatch; preserve historical model mentions as history, never use them as live routes.
- GPT 5.6 Sol handles backend implementation and independent review where assigned. Discover and verify the exact available route rather than guessing from a friendly label.
- Separate author from verifier. Sol cannot approve its own backend change; use independent Fable/Astra review as appropriate. A model role is a current user preference, not proven model superiority.
- Board seats differ from workers. Current board insight providers are Astra and Fable only. The main coordinator can resolve ordinary technical disagreement within delegated authority, recording reasons and dissent instead of fabricating consensus.

## Decisions and debate
1. Separate confirmed user decisions, open questions, tentative ideas and agent proposals. A /btw checkpoint needs a durable decisions-only continuation prompt because temporary context may not persist.
2. Follow corrections. Challenge only a material misunderstanding or omission supported by clear reasoning/evidence, not preferences merely because you disagree.
3. Ask each coordinator to derive its own precise goal and acceptance checks from the assigned mission. Include intent, non-goals, evidence, allowed writes, dependencies, routes, resource budget, stop conditions and final output contract.
4. Default to at most three total Astra/Fable debate rounds per important decision. Stop earlier when resolved. Use primary evidence and targeted tests. Record alternatives, accepted/rejected critiques, and residual uncertainty.
5. Do not escalate every tie. The coordinator resolves routine technical tradeoffs. Escalate reserved human gates, material product direction, safety/authority changes, destructive scope, credentials/access, spending and external commitments. Initial planning can require more Brayan involvement. Missing approval is not a technical tie to override.
6. Use realistic task-specific deadlines and bounded retries. Do not impose an arbitrary short timeout as permanent governance. Distinguish healthy slow work from a stalled process.

## Workspaces and decomposition
- Launch every agent in its actual project workspace or prepared worktree. Record execution cwd separately from its report/log directory and verify the child's cwd/branch.
- Independent projects get independent coordinators. Split complex work into dependency-aware deliverables; give Grok/Sol bounded contracts instead of the whole project. Avoid tiny splits with more coordination overhead than benefit.
- Each writer owns disjoint paths or its own worktree. Inspect dirty state, HEAD and repo instructions before editing. Never restore/stage/commit unrelated work. Serialize shared registry/config writes.
- Bound global concurrency including descendants. Start with one heavy build/implementation at a time and increase only with measured capacity and independent ready work. No recursive fanout by default.
- Use independent Hermes CLI processes for long steerable missions: terminal background=true, notify=true; explicit model/provider/effort, --query-file, --oneshot and run/turn budgets when installed CLI supports them. Persist session/PID/log/exit/result. Verify startup once, then react to completion rather than LLM polling.
- Headless CLI runs are normal saved chats, not live attachable REPLs. Never resume the same active session in a competing writer. Use supported interactive control or STEERING.md read at phase boundaries; urgent steering needs explicit acknowledgment.
- Coordinators must collect and verify their children before exit, not orphan background work.
- Do not assume delegate_task inherits the active model. Its effective configured route can differ, and its exposed schema may offer no per-call pin. For required Astra sessions, use explicitly pinned independent Hermes CLI launches. Verify dispatch metadata and disclose any model mismatch; never describe a Luna helper as Astra.

## Minimal coordinator workspace
Use a task-owned control directory alongside execution workspaces, not the vault as a build directory. Keep DECISIONS.md, WORKSTREAMS.json, per-lane MISSION/GOAL/STEERING/STATUS, session log, RESULT.json, external EXIT.json, and PARENT_REVIEW.md. CONTINUE.md contains confirmed decisions and verified state, with proposals/pending work labeled separately. This is an organization pattern, not a new daemon requirement.

Herdr is an optional candidate interactive backend. Read references/herdr-evaluation.md before installing/adopting it. Pane lifecycle is not task acceptance.

## Resource safety
Check live available RAM, swap activity, CPU/load, disk and GPU if relevant before dispatch and intensive tests. Include nested workers, browsers, test processes and dev servers in fleet capacity. Hardware memory is not a capacity check. scripts/resource_probe.py offers a read-only Linux snapshot and bounded sampling.

Monitor long/intensive work with cheap deterministic sampling or an existing supervisor, not repeated agent turns. Record pressure and recheck at phase changes. Under sustained memory pressure, swapping, I/O load or poor responsiveness, pause NEW dispatch and reduce owned test/build concurrency. Stop only owned nonessential jobs when justified; never kill unrelated processes. Numerical thresholds are task configuration, not universal safety guarantees.

## Verify four separate facts
1. Exited: an external wrapper waited for the exact child and recorded exit/signal/deadline. Popen success or PID disappearance is insufficient.
2. Validated: required artifacts exist, schema and acceptance checks pass, and independent tests exercise the delivered revision. Exit zero or self-written PASS is insufficient.
3. Delivered: transport success plus exact target/message ID or supported read-back. Without a receipt delivery is unknown.
4. Acknowledged: Brayan replied or explicitly acknowledged. Transport success does not prove reading.

For Fable inspect raw JSON is_error=false and actual modelUsage, explicit session ID and requested effort. Disclose auxiliary usage without inventing extra board votes. Never implicit --continue across concurrent Claude sessions. Keep unmeasured cost unknown.

On completion inspect original artifacts/diffs/errors and rerun checks into fresh outputs. Add unseen adversarial cases where correctness matters. Attribute parent repairs separately from child work. Preserve partial/blocked states. Mocks prove local behavior, not live integration. Frozen review approval does not apply to later code revisions.

Give compact outcomes, decisions needed and useful paths. Completion notifications depend on parent platform/liveness; local-only cron does not message an inactive CLI.

## Experiments and recurring-state resets
For bakeoffs freeze product, production acceptance, native-harness policy, route/budget controls and epoch. Zero-start candidates each have their own coordinator and cannot copy prior solutions. Different products, mixed epochs, translated failures and raw test counts do not establish a causal winner. Current next-bakeoff direction requires a production scheduler deliverable; the earlier runner prototype is insufficient. Establish an operational acceptance contract before launch.

Use Fable functional testing of the new approach before expanding the next bakeoff: execute realistic workflows and independent failures, not merely read architecture. Save raw results and limitations.

For a new-model recurring-report reset, inventory exact generated outputs and preserve a hashed recoverable baseline outside active context. Clear only authorized generated notes. Keep agent definitions, raw sources, decisions and project evidence. Verify references and recreation behavior. A model swap does not repair deterministic code defects.

## Brief AGENTS.md
Keep essential constraints, precedence and a map to canonical procedures. Move lengthy detail into linked docs without dropping source-preservation, safety or authority rules. Avoid duplicating entire workflows across AGENTS, skills and prompts.

## Completion checks
Verify workspace/ownership, actual routes, recorded decisions, bounded worker tasks, resource checks, exact output and parent acceptance. Relay user steering to affected lanes. Save a decisions-only continuation prompt. No approval bypass, unowned cleanup, orphaned worker or fabricated result.
