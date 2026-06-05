# Comparative Bakeoff Orchestration

Use this when Brayan wants to compare several agent methodologies, frameworks, tools, or workflows by having each independently solve the same small implementation task.

## Trigger

A request has this shape:

- several approaches/tools/skill packs/harnesses are listed;
- the implementation project is TBD or should be chosen separately;
- each approach should be tested as intended, not reduced to a generic prompt;
- results should be comparable across independent versions;
- Brayan wants likes/dislikes/errors and user-intervention burden recorded.

## Recommended scaffold

Create one coordination workspace under `/home/brayan/projects/<slug>/` with:

- `README.md` — orientation and next steps.
- `PROJECT_STATUS.md` / `PROJECT_CHANGELOG.md` — active project control files when this is a registered active project.
- `PROJECT_SPEC.md` — concise user-fillable file for the shared TBD implementation task.
- `EVALUATION_PROTOCOL.md` — fairness rules, evidence requirements, scoring dimensions, and pass/fail boundaries.
- `APPROACH_PRIORITY.md` — priority order and rationale.
- `USER_FEEDBACK.md` — Brayan's likes/dislikes/clear errors/manual interventions per approach.
- `SETUP_FINDINGS.md` — cross-approach setup findings and blockers discovered during scaffolding.
- `approaches/<NN-slug>/` — one independent git repo per approach.

Each approach repo should start with:

- `README.md`
- `APPROACH.md` — intended upstream usage, setup notes, fidelity caveats, future run command shape.
- `AGENTS.md` — local agent instructions for the approach run.
- `RUN_LOG.md` — commands, prompts, interventions, verification outputs.
- `RESULT.md` — final pass/fail, scorecard, adoption verdict.
- `.gitignore`

## Orchestration pattern

1. Register or update the project control layer if this is a real active project.
2. Preserve the user's raw approach list in the vault if it arrived through notes intake.
3. Build the coordination workspace before attempting implementation.
4. Use independent setup subagents for approach folders when there are many approaches. Give each subagent a narrow task: inspect the upstream source, scaffold docs, initialize git, and report commit/status. Do not let setup agents start the TBD implementation.
5. Verify all approach repos exist, have required files, and have clean git status.
6. Only after Brayan locks `PROJECT_SPEC.md`, launch implementation runs in priority order.
7. Enforce fairness: same locked spec, no copying between approaches, explicit logging of manual intervention, and real test/demo outputs.

## Priority-order heuristic

Rank by likely seriousness for disciplined, reproducible engineering:

1. explicit methodology/process and verification discipline;
2. production-grade skills and testing/review norms;
3. observability/replay/policy-bound execution;
4. acceptance pipeline or other objective quality gates;
5. sandbox/isolation/harness support;
6. tool-specific configs;
7. broad experimental/operator systems;
8. role-heavy/vibe-coded systems.

This is a starting heuristic. Adjust when the user's stated goal or project stack makes an approach more or less relevant.

## Pitfalls

- Do not ask Brayan to choose every folder shape when the obvious coordination scaffold is enough.
- Do not begin implementation before the shared spec is locked.
- Do not count setup failures as coding failures; log them separately.
- Do not install global tool configs for approach-specific systems when an isolated home/config can preserve fidelity without mutating Brayan's normal environment.
- Do not treat missing local binaries or API keys as durable skill constraints; record them in the workspace `SETUP_FINDINGS.md`, not in persistent skill doctrine.
- Do not accept a methodology's self-description as evidence of quality; require run logs, diffs, tests, and Brayan's observed friction/error notes.
