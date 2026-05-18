# Brayan current file-defined Hermes agent organization

This reference records the current live organization for Brayan/Darwin recurring and specialized Hermes agents. Keep the main `file-defined-hermes-agents` skill procedural; update this reference when the live organization changes.

## Canonical skill categories

Automation agents live under:

```text
~/.hermes/skills/automation-agents/<agent-name>/SKILL.md
```

Current automation-agent skills:

- `daily-review-agent` — `~/.hermes/skills/automation-agents/daily-review-agent/SKILL.md`
- `decision-reminders-agent` — `~/.hermes/skills/automation-agents/decision-reminders-agent/SKILL.md`
- `inbox-triage-agent` — `~/.hermes/skills/automation-agents/inbox-triage-agent/SKILL.md`
- `notes-intake-agent` — `~/.hermes/skills/automation-agents/notes-intake-agent/SKILL.md`
- `topic-recommendations-agent` — `~/.hermes/skills/automation-agents/topic-recommendations-agent/SKILL.md`
- `vault-structure-auditor-agent` — `~/.hermes/skills/automation-agents/vault-structure-auditor-agent/SKILL.md`
- `hermes-upstream-rebase-ci-agent` — `~/.hermes/skills/automation-agents/hermes-upstream-rebase-ci-agent/SKILL.md`

Opportunity workflow skills live under:

```text
~/.hermes/skills/automation-agents/opportunities/<skill-name>/SKILL.md
```

Current opportunity skills:

- `opportunity-intake-agent` — `~/.hermes/skills/automation-agents/opportunities/opportunity-intake-agent/SKILL.md`
- `opportunity-preparation-agent` — `~/.hermes/skills/automation-agents/opportunities/opportunity-preparation-agent/SKILL.md`
- `opportunity-closing-agent` — `~/.hermes/skills/automation-agents/opportunities/opportunity-closing-agent/SKILL.md`

General design skill:

- `file-defined-hermes-agents` — `~/.hermes/skills/file-defined-hermes-agents/SKILL.md`

Retired automation/design skills:

- `darwin-personal-automation` — retired and absorbed into `file-defined-hermes-agents`; do not recreate unless there is a genuinely new class-level purpose.

Vault support skill:

- `personal-vault-ops` — `~/.hermes/skills/note-taking/personal-vault-ops/SKILL.md`

## Agent prompt/template files

Current prompt/template files under `~/.hermes/agents/`:

- `daily-review/prompt-template.md`
- `decision-reminders/prompt-template.md`
- `inbox-triage/prompt-template.md`
- `notes-intake/prompt-template.md`
- `notes-intake/preprocessor-instructions.md`
- `topic-recommendations/prompt-template.md`
- `vault-structure-auditor/prompt-template.md`
- `opportunity-preparation/prompt-template.md`
- `opportunity-closing/prompt-template.md`
- `hermes-upstream-rebase-ci/prompt-template.md`
- `autoresearch-commander/README.md`
- `autoresearch-commander/mission-template.md`
- `autoresearch-commander/codex-supervisor-notes.md`

## Dispatcher scripts

Current mechanical dispatcher / pre-run scripts under `~/.hermes/scripts/`:

- `inbox_triage_wake_gate.py`
- `opportunity_preparation_ready_scan.py`
- `opportunity_scaffold.py`
- `opportunity_closeout_scan.py`
- `vault_structure_audit.py`
- `hermes_upstream_rebase_ci.py`

## Recurring cron bindings

Current recurring cron jobs load canonical skills by bare name:

- `darwin-daily-review`
  - skills: `personal-vault-ops`, `daily-review-agent`
  - schedule: `0 9 * * *`
- `darwin-topic-recommendations`
  - skills: `personal-vault-ops`, `topic-recommendations-agent`
  - schedule: `0 19 * * *`
- `darwin-inbox-triage`
  - skills: `personal-vault-ops`, `inbox-triage-agent`
  - script: `inbox_triage_wake_gate.py`
  - schedule: `0 10,18 * * *`
  - wake gate: skips the agent when `~/personal_vault/inbox/` has no actionable items beyond `README.md` / hidden-noise files
- `darwin-decision-reminders`
  - skills: `personal-vault-ops`, `decision-reminders-agent`
  - schedule: `0 12,17 * * *`
- `darwin-opportunity-preparation-agent`
  - skills: `personal-vault-ops`, `opportunity-preparation-agent`
  - script: `opportunity_preparation_ready_scan.py`
  - schedule: `0 11 * * *`
- `darwin-opportunity-closing-agent`
  - skills: `personal-vault-ops`, `opportunity-closing-agent`
  - script: `opportunity_closeout_scan.py`
  - schedule: `30 11 * * *`
- `hermes-upstream-rebase-ci`
  - skills: `hermes-agent`, `systematic-debugging`, `personal-vault-ops`, `hermes-upstream-rebase-ci-agent`
  - script: `hermes_upstream_rebase_ci.py`
  - schedule: `30 9 * * *`
- `vault-structure-auditor`
  - skills: `personal-vault-ops`, `vault-structure-auditor-agent`
  - script: `vault_structure_audit.py`
  - schedule: `0 10 * * 0`

## Organization rules

- Keep operational behavior in canonical operational skills, not in this reference.
- Keep Brayan-specific runtime inventory here, not in the main `file-defined-hermes-agents` body.
- Keep cron skill lists as bare names unless disambiguation becomes necessary.
- If a skill moves category, preserve the frontmatter `name:` and verify `skill_view(<bare-name>)` still resolves.
- If an automation is retired, remove its cron/script/template references, clean stale `.usage.json` metadata if necessary, sync the personalization bundle, and update this file in the same cleanup.
