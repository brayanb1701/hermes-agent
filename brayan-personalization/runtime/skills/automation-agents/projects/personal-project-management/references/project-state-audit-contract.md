# Project state audit contract

The deterministic audit script is `~/.hermes/scripts/project_state_audit.py`.

It checks status vocabulary, dashboard/backlog/finished membership, active required fields, workspace existence, required control files, seed workspace absence, paused metadata, finalized records, pending closeout/reopen selection, Web Friction Interrupter area, register links, and skill-reference drift.

It is report-only. Findings become actionable through interactive Darwin sessions or the existing `vault-structure-auditor` cron agent after Brayan reviews patch proposals.

Run:

```bash
python3 ~/.hermes/scripts/project_state_audit.py --dry-run
python3 ~/.hermes/scripts/project_state_audit.py --json
python3 ~/.hermes/scripts/vault_structure_audit.py
```
