# Opportunity-preparation file-defined agent pattern

This is Brayan's concrete example of the independent-session fanout pattern. It belongs in a reference because it is workflow-specific, while the main `file-defined-hermes-agents` skill should stay reusable.

## Intended architecture

- The recurring cron job is `darwin-opportunity-preparation-agent`.
- The cron job runs once daily.
- The pre-run script is `~/.hermes/scripts/opportunity_preparation_ready_scan.py`.
- The script scans `~/personal-vault/opportunities/<slug>/opportunity.md` records.
- Launchable records have:
  - `status: preparation-ready`
  - `automation_route: opportunity-preparation`
- The script selects at most three highest-priority launchable opportunities.
- The script launches one independent Hermes session per selected opportunity.
- The launched session loads `personal-vault-ops` and `opportunity-preparation-agent`.
- The launched session uses `~/.hermes/agents/opportunity-preparation/prompt-template.md` as the per-item prompt shape.
- The preparation agent is adaptive: it follows mode-specific references based on `workflow_mode`.

## Non-goals

- Do not use plugin handoffs or immediate triggers for this workflow unless Brayan explicitly redesigns the cadence.
- Do not use `delegate_task` for the per-opportunity processing; Brayan wants separate independent sessions per item.
- Do not embed long natural-language instructions in `opportunity_preparation_ready_scan.py`.
- Do not submit applications, forms, public PRs, payments, or other external actions without explicit approval.

## Expected output behavior

A preparation session should:

1. Read the opportunity record and linked/source details.
2. Inspect the relevant vault/project/profile context.
3. Create or update `opportunities/<slug>/application/preparation-packet.md`.
4. Update the opportunity record to `awaiting-review` when the packet is ready.
5. Notify Brayan concisely with the path and review status.

## Verification

- `python -m py_compile ~/.hermes/scripts/opportunity_preparation_ready_scan.py`
- Dry-run shows ready count, selected count, max count, wake gate, and errors.
- No long task prompt is embedded in the scanner script.
- `skill_view("opportunity-preparation-agent")` resolves by bare name.
- The cron job still loads `personal-vault-ops` and `opportunity-preparation-agent`.
