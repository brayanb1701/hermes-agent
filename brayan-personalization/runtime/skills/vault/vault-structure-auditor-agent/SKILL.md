---
name: vault-structure-auditor-agent
description: "Stable behavior for Darwin's recurring Vault v2 structure auditor: detect drift, broken links, wrong-folder notes, opportunity/application inconsistency, and propose exact patches without autonomously moving/deleting content."
version: 1.0.0
author: Darwin
license: MIT
---

# Vault Structure Auditor Agent

Use this skill for scheduled or manual audits of Brayan's personal vault structure.

## Mission

Keep Vault v2 clean and semantically consistent:

- `projects/` = true execution projects only, one folder per project with `README.md`.
- `opportunities/` = one folder per opportunity, with `opportunity.md` and optional `application/` materials.
- `_meta/` = schema, workflows, architecture, guides, templates, logs, dashboards, audits, principles.
- `profile/` = CV/bio/portfolio/application support.
- `decisions/` = pending decisions and decision logs.
- `references/` = passive shelf resources.
- `queries/` = active queues/syntheses.
- `domains/` = navigation hubs, not operational databases.
- `raw/` = immutable source material.
- `inbox/` = transient unprocessed manual files only.

## Required reads

1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/vault-organization-v2.md`
3. `~/personal_vault/_meta/routing-matrix.md`
4. The latest audit report under `~/personal_vault/_meta/audits/`
5. Directly relevant notes for any proposed patch group

## Deterministic script

Primary inventory is produced by:

`~/.hermes/scripts/vault_structure_audit.py`

It writes:

`~/personal_vault/_meta/audits/YYYY-MM-DD-vault-structure-audit.md`

The script checks:

- files by top-level folder;
- frontmatter `type`, `status`, and `area` values;
- notes in `projects/` that are not `projects/<slug>/README.md` project hubs;
- project notes missing next-action wording;
- active references to retired Vault v1 paths;
- broken wikilinks;
- opportunity records with packet/status inconsistency;
- passive references accidentally treated as active queue items;
- git status at audit time.

## Output behavior

When issues exist, produce:

1. high-level diagnosis;
2. affected paths;
3. patch proposal groups with exact intended edits/moves;
4. risk level and whether Brayan approval is required;
5. recommended next action.

When no issues exist, return `[SILENT]` unless there is a genuinely useful maintenance note.

## Allowed without approval

In an interactive user-requested cleanup session, after reading the affected files:

- fix obvious frontmatter formatting;
- update generated dashboards;
- repair stale links caused by an already-approved migration;
- add missing index links;
- write audit reports.

## Never allowed without explicit Brayan approval

- delete raw material;
- delete project/opportunity/concept/profile notes;
- archive active P0/P1 items;
- move large groups of files;
- change priorities except from explicit user corrections or deterministic policy;
- rewrite application materials;
- submit anything externally.

## Patch proposal standard

A patch proposal should be concrete enough that a later interactive Darwin session can execute it in one pass:

- exact file paths;
- exact old/new folder target when moving;
- exact link rewrite rule;
- expected validation command;
- rollback note when relevant.

## Verification

After any approved cleanup:

- run `python3 ~/.hermes/scripts/vault_structure_audit.py`;
- run `git diff --check` in `~/personal_vault`;
- run the job-tailoring dry run if opportunity paths or packet fields changed;
- report remaining issues separately from fixed issues.
