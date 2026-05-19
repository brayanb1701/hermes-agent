# Opportunity-closeout file-defined agent pattern

This reference captures the implementation pattern for Brayan's opportunity closeout workflow. It belongs here because the main `file-defined-hermes-agents` skill should stay class-level, while this is a concrete workflow pattern similar to opportunity preparation.

## Intended architecture

The closeout workflow should be file-driven and handled by its own specialized opportunity agent, not folded into intake or preparation.

Preferred runtime surfaces:

```text
~/.hermes/skills/automation-agents/opportunities/opportunity-closing-agent/SKILL.md
~/.hermes/agents/opportunity-closing/prompt-template.md
~/.hermes/scripts/opportunity_closeout_scan.py
cron job: darwin-opportunity-closing-agent
```

Deterministic scaffold surfaces:

```text
~/personal_vault/_meta/templates/opportunity-closeout-input-template.md
~/.hermes/scripts/opportunity_scaffold.py
~/personal_vault/opportunities/<slug>/closeout-input.example.md
```

## Closeout input contract

- The scanner processes only live files named exactly `closeout-input.md` under `opportunities/<slug>/`.
- The scanner must ignore `closeout-input.example.md`.
- The `.example` file exists so Brayan has the structure available from the start without relying on the intake agent to hand-write repetitive boilerplate.
- The live `closeout-input.md` should be created by copying/renaming the example and filling facts.
- Processed closeout inputs should be preserved as evidence and marked complete/processed, not deleted.

## Scaffold script pattern

Use a deterministic helper such as:

```bash
python3 ~/.hermes/scripts/opportunity_scaffold.py --opportunity ~/personal_vault/opportunities/<slug>/opportunity.md
python3 ~/.hermes/scripts/opportunity_scaffold.py --all --examples-only --dry-run
python3 ~/.hermes/scripts/opportunity_scaffold.py --all --examples-only
```

Expected behavior:

1. Read the opportunity record.
2. Resolve slug and title.
3. Render `_meta/templates/opportunity-closeout-input-template.md`.
4. Create `closeout-input.example.md` only if missing.
5. Never create live `closeout-input.md` unless an explicit live-closeout option is added and requested.
6. Never overwrite existing examples unless a force flag is explicit.
7. Emit compact JSON for verification.

## Closing scanner pattern

The mechanical dispatcher should mirror the opportunity-preparation scanner:

- scan `opportunities/*/closeout-input.md`;
- parse minimal frontmatter;
- require `status: pending`;
- require `proposed_status: applied|archived`;
- skip `complete`, `paused`, and malformed inputs;
- sort by priority and slug;
- launch at most a small bounded number of independent Hermes sessions;
- write lock/log files under `~/.hermes/state/opportunity_closing_sessions/` and `~/.hermes/logs/opportunity_closing_sessions/`;
- emit wake-gated JSON so the cron parent stays silent when no work exists.

## Closing agent behavior

The independent closeout session loads `personal-vault-ops` and `opportunity-closing-agent` and processes exactly one closeout input.

It should:

1. Read schema/index/log, the opportunity closing workflow, the final-result template, the closeout input, and the opportunity note.
2. Validate status/result consistency:
   - `applied` is final for submitted/applied opportunities.
   - `archived` is final for closed/no-submission/expired/skipped/etc.
   - avoid `status: archived` with `result_status: submitted`.
3. If facts are insufficient, do not mutate final state; set the input to `paused`, append missing-info notes, and notify Brayan.
4. If facts are sufficient, update `opportunity.md`, remove from `opportunities/dashboard.md`, add to `opportunities/finished.md`, clean stale decisions, append `_meta/log.md`, and mark the input complete/processed.
5. Create `opportunities/<slug>/post-application/` only when an applied opportunity needs ongoing follow-up tracking.

## Cron pattern

A reasonable schedule is after opportunity preparation and before decision reminders, for example:

```text
30 11 * * *
```

Cron should use:

- skills: `personal-vault-ops`, `opportunity-closing-agent`
- script: `opportunity_closeout_scan.py`
- delivery: same user-facing target as other Darwin opportunity agents, unless Brayan chooses otherwise

The parent cron prompt should remain fallback/reporting only. It should not perform closeout work directly except for trivial dispatcher failure diagnosis.

## Verification

Before enabling cron:

```bash
python3 -m py_compile ~/.hermes/scripts/opportunity_scaffold.py
python3 -m py_compile ~/.hermes/scripts/opportunity_closeout_scan.py
python3 ~/.hermes/scripts/opportunity_scaffold.py --all --examples-only --dry-run
python3 ~/.hermes/scripts/opportunity_closeout_scan.py --dry-run
```

Expected initial closeout scan when no live inputs exist: `ready_count: 0` and no launch. Example files must not appear as launchable.
