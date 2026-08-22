# Opportunity closeout implementation case notes — 2026-05-18

Use as a concrete example for a vault workflow migration that also changes Hermes runtime automation.

## What made this migration reusable

The opportunity closeout work crossed three layers at once:

1. Vault docs/templates/registers:
   - `_meta/schema.md`
   - `_meta/workflows/opportunities/*`
   - `_meta/templates/opportunity-*`
   - `opportunities/dashboard.md`
   - `opportunities/finished.md`
2. Runtime automation:
   - local agent skill under `~/.hermes/skills/automation-agents/opportunities/`
   - prompt template under `~/.hermes/agents/opportunity-closing/`
   - deterministic scripts under `~/.hermes/scripts/`
   - cron job binding
3. Personalization bundle:
   - runtime assets synced into `~/.hermes/hermes-agent/brayan-personalization/runtime/...`

The implementation should be treated as one migration contract, not separate unrelated edits.

## Durable workflow lesson

Keep the schema compact and structural. In this session, workflow-specific opportunity closeout policy initially risked making `_meta/schema.md` too long and policy-heavy. The better final shape was:

- `_meta/schema.md`: canonical folders, status vocabulary, broad metadata, and links to workflows.
- `_meta/workflows/...`: lifecycle policy and human/process semantics.
- runtime skills: executable agent behavior and boundaries.
- `_meta/tmp_analysis/...`: rejected alternatives, rationale, and detailed planning notes.

Do not repeat rejected alternatives in active canonical docs unless the user explicitly wants a warning. Prefer direct positive policy in canonical surfaces.

## Verification pattern used

For migrations like this, verify all affected layers:

- `cd ~/personal-vault && git diff --check`
- `cd ~/.hermes/hermes-agent && git diff --check`
- compile changed scripts, e.g. `python3 -m py_compile ~/.hermes/scripts/<script>.py`
- dry-run scanners/dispatchers, e.g. `python3 ~/.hermes/scripts/opportunity_closeout_scan.py --dry-run`
- search active docs/skills for retired fields or rejected-design terms
- inspect generated artifacts after applying scaffold helpers, not just JSON dry-run counts
- run the runtime personalization sync after live runtime skill/agent/script changes and inspect the bundle diff

## Pitfalls from this case

- Do not let an approved implementation plan become the final architecture document. Plans can contain rejected alternatives, open questions, and too much policy detail for canonical files.
- Do not manually hand-write repetitive `.example` files when a deterministic scaffold can render them from a template.
- Do not treat dashboard/register edits as sufficient if runtime activation surfaces still point at older behavior.
- Do not process real live closeout inputs during infrastructure implementation unless Brayan explicitly approves that side effect.
