---
name: personal-vault-ops
description: Operate Brayan's unified personal vault at ~/personal_vault — a combined Obsidian vault and LLM wiki used by Darwin for capture, routing, linking, reviews, and project support.
version: 1.1.0
author: Darwin
license: MIT
---

# Personal Vault Ops

Use this skill whenever work touches Brayan's second brain, notes, wiki, inbox, project routing, topic recommendations, opportunities, or vault maintenance.

This is the stable vault navigation and management skill. It should explain how the vault works, not preserve one-time migration plans or duplicate operational agent runbooks.

## Vault location

- `~/personal_vault`

## Orientation order

At the start of any vault-related session, read:

1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. Any directly relevant domain/project/workflow notes

## Core principle

This is one unified system:

- Obsidian vault
- LLM wiki
- Darwin's operating memory substrate for structured knowledge

Do not split them mentally into separate systems unless Brayan asks.

## Folder roles

- `_meta/` — vault operating layer: schema, index, routing, log, architecture, workflows, principles, guides, templates, audits, and migration history.
- `raw/` — immutable source material, assets, papers, articles, transcripts, and original captures.
- `domains/` — navigation hubs by area.
- `concepts/` — durable reusable ideas/models that are not passive tool references.
- `queries/` — active reading/research/watch/practice queues and saved syntheses.
- `references/` — passive tools/resources/cookbooks/pricing/infrastructure references used when needed.
- `projects/` — project hubs and project-level indexes; each actual project has `projects/<slug>/README.md`; finished projects are registered in `projects/finished.md` and meaningful finished projects normally have `projects/<slug>/closeout.md`.
- `opportunities/` — jobs, fellowships, grants, scholarships, challenges, bounties, funding leads, and co-located application materials; finished opportunities are registered in `opportunities/finished.md`.
- `profile/` — canonical CV, bio, portfolio, and application profile sources.
- `decisions/` — pending decisions and decision logs.
- `daily/` — reviews and snapshots.
- `inbox/` — transient unprocessed manual files only; often empty.
- `comparisons/` — side-by-side analyses when needed.

## Project code workspace convention

When Brayan starts a real coding/research project, keep runnable repositories and generated experiment artifacts outside the vault under `/home/brayan/projects/<repo-or-experiment>/`.

The vault `projects/<slug>/README.md` remains the documentation/control layer: objective, constraints, success levels, links to live workspaces, decisions, stop conditions, and postmortem. For autonomous experiment commanders, link live files such as `FEEDBACK.md`, `COMMANDER_STATUS.md`, and `EXPERIMENTS.tsv` from the vault project note instead of copying bulky logs into the vault.

For project lifecycle/workspace-control design, keep two layers distinct:

- Vault layer: `~/personal_vault/projects/<slug>/README.md`, dashboards/registers, workflow docs, and final closeout records.
- Workspace layer: `/home/brayan/projects/<slug>/` for active development, runtime artifacts, and live status/change files.

For active coding/research projects, prefer a required workspace control pair from activation onward: `PROJECT_STATUS.md` for the current snapshot and `PROJECT_CHANGELOG.md` for chronological, parser-friendly updates. Do not rely on the vault README alone to infer live project state.

For the reusable setup pattern, see `references/project-workspace-control-layer.md`.

## Important hubs

- `domains/ai/ai-map.md`
- `domains/physics/physics-map.md`
- `domains/coding/coding-map.md`
- `domains/creative/creative-map.md`
- `domains/economy/economy-map.md`
- `domains/opportunities/opportunities-map.md`
- `projects/dashboard.md`
- `projects/finished.md`
- `opportunities/dashboard.md`
- `opportunities/finished.md`
- `_meta/workflows/projects/project-closing-workflow.md`
- `_meta/workflows/opportunities/opportunity-closing-workflow.md`
- `projects/darwin-improvement/README.md`
- `queries/topic-recommendations.md`

## Filing rules

- Raw capture stays raw first.
- For text captures promoted out of `inbox/`, preserve original wording as an immutable raw note in `raw/notes/` before distilling.
- Unclear or still-processing items go to `inbox/`.
- `inbox/` is transient triage, not durable storage.
- Once an item is confidently routed into a durable destination, remove it from `inbox/` rather than keeping duplicate content there.
- Durable knowledge goes to `concepts/`, `domains/`, `comparisons/`, or `queries/`.
- Actionable execution goes to `projects/`.
- Assistant-improvement ideas usually link to `projects/darwin-improvement/README.md`; upstreamable Hermes framework fixes use the isolated `/home/brayan/projects/hermes-agent-upstream-prs` workspace.
- Income, trading, and monetization ideas usually link to `domains/economy/economy-map.md`.
- Jobs, internships, fellowships, grants, scholarships, bounties, competitions, and funding leads usually link to `domains/opportunities/opportunities-map.md` and/or create records under `opportunities/`.

## Maintenance rules

- Prefer `[[wikilinks]]`.
- Add important pages to `_meta/index.md`.
- Append meaningful structural changes to `_meta/log.md`.
- Keep domain notes as navigation hubs, not giant dumps.
- Avoid polluting durable notes with low-confidence OCR output or raw scraps.
- When maintaining `opportunities/dashboard.md`, keep the table sorted as Brayan's review queue: exact `P0`, mixed/ranged `P0/P1` or `P0-P1`, exact `P1`, mixed/ranged `P1/P2` or `P1-P2`, exact `P2`, mixed/ranged `P2/P3` or `P2-P3`, then exact `P3`.
- When Brayan says a project or opportunity is finished, awarded, rejected, expired, closed, archived, submitted/no-longer-actionable, or asks for a final result/postmortem/retrospective, use the dedicated closing workflow before editing records: `_meta/workflows/projects/project-closing-workflow.md` for projects and `_meta/workflows/opportunities/opportunity-closing-workflow.md` for opportunities.
- For automation-ready finalization, prefer an explicit item-level input file such as `closeout-input.md` or `final-result-input.md` containing the outcome/evidence/blockers over relying only on trigger phrases. The closing workflow should then fold that input into the canonical opportunity record or project closeout, update dashboards/registers/decisions, and preserve the input when it contains user wording/evidence or when the domain workflow says preservation is canonical.
- For opportunity closeout specifically, preserve processed `opportunities/<slug>/closeout-input.md` as part of the opportunity evidence trail and mark it complete/processed rather than deleting it; `closeout-input.example.md` is only a scaffold/guide and should be ignored by closeout scanners.
- Active/current dashboards should not silently accumulate finalized items. Finished projects go to `projects/finished.md`; finished opportunities go to `opportunities/finished.md`. For project lifecycle design, keep `projects/dashboard.md` focused on active projects; seed and paused projects belong in a backlog/incubation-style surface or their own project notes, not mixed into the active table. Status tracks workflow state; `result_status`, `result_type`, and `result_summary` track final outcome.
- Treat `_meta/schema.md` as the source of truth for vault structure. Skills should point to schema and encode behavior; avoid duplicating exact structural policy or turning a one-path migration into broad placement prohibitions unless schema itself says so.
- Keep root `README.md` files as lightweight orientation pages, not operational dashboards. For projects and opportunities, active/current tables belong in `dashboard.md`, finalized records in `finished.md`, and root READMEs should explain folder purpose, record shape, and canonical links.
- When closing opportunities with linked projects, classify the project check as `not-needed`, `continue-project`, `close-project`, or `needs-review` rather than assuming the project ends automatically.
- When removing duplicate binary uploads from `inbox/` after promotion to `raw/assets/`, verify byte identity first with hashes/checksums, then update any raw source note that points at the transient `inbox/` path.

## Current architecture docs

Read these when relevant:

- `~/personal_vault/_meta/architecture/notes-intake-ingestion-pipeline.md`
- `~/personal_vault/_meta/workflows/notes-intake/ocr-workflow.md`
- `~/personal_vault/_meta/architecture/review-cron-system.md`
- `~/personal_vault/_meta/architecture/vault-access-layer.md`
- `~/personal_vault/_meta/routing-matrix.md`
- `~/personal_vault/_meta/architecture/local-ai-stack.md`

## Current runtime helpers

- Telegram notes intake group: `Anything Inbox` (`chat_id: -1003960601334`).
- Enabled Hermes plugin: `notes_preprocessor`.
- Anything Inbox uses `notes_intake.auto_new_session_per_capture: true`, so each new capture normally runs in a fresh gateway session.
- If multiple URLs/fragments are related, Brayan should send them in the same Telegram message.
- Local OCR/STT packages are available through `~/.hermes/venvs/ocr`.
- The live notes-intake image pipeline currently uses local OCR first and main-provider vision fallback when needed.

## Recommended behavior

When working with the vault:

1. Orient.
2. Preserve raw input.
3. Classify intent.
4. Route to the correct note layer.
5. Add links.
6. Update index/log if the structure changed.
7. Verify by rereading changed files and searching for key links/slugs.

## Application/profile support writing

When drafting support material from `profile/` or `opportunities/<slug>/application/` for recommenders, applications, or profile packets:

- Respect Brayan's requested language, but preserve official names/titles in their original form unless he explicitly asks for translation. Examples: `International Physicists' Tournament`, `Colombian Physicists' Tournament`, `Industrial University of Santander`, `Computer Systems Engineering`, `Physics`, `Geo2Code I Hackathon`, `Co-Afina 2023 Hackathon`.
- If the recipient only needs a source list or recommender input, default to concise bullets, not a polished long letter. Include only the requested scope; if Brayan says no professional experience, exclude all professional roles and keep academic items only.
- For recommender-letter drafts, avoid putting words too strongly in the recommender's mouth. Prefer a simple data section, relationship context, optional points the recommender may mention, then a short editable draft.
- If Brayan asks for a recommender/support draft to match another letter's style, inspect the actual saved source first. For a local PDF, extract text with `pdftotext <file.pdf> -` when available, then mirror its level of formality, header layout, paragraph length, and closing rather than inventing a new style.
- When adding a translation or second-language version to an existing draft, reread the current saved source text first and mirror Brayan's latest edits closely. Do not translate from an earlier assistant version or reintroduce phrasing Brayan softened/removed.
- If Brayan requests a plain-text application/support file, save `.txt` with no frontmatter or markdown formatting.
- When adapting an existing application answer or letter for a similar opportunity, reuse the proven structure and tone, but explicitly re-anchor the opening, team/domain, role functions, and examples to the new posting. Keep the result natural and concise rather than visibly templated.
- For application fields with a hard character limit, compute and record the character count in the draft metadata/body, then iterate until it is within limit; if a plain-text copy exists, keep the `.md` and `.txt` versions synchronized.
- When Brayan provides a new opportunity excerpt and asks for an adapted application material, create or update the opportunity folder only when useful, preserve the user-provided excerpt in a minimal opportunity record if no fuller record exists, and update `opportunities/dashboard.md` in priority order if the item should enter the review queue.
- If Brayan requests a quick PDF application/support letter, create an editable HTML source alongside the PDF and render with `weasyprint` when available; verify with `file <pdf>` and `pdftotext <pdf> - | head -c ...` to catch missing text/layout issues.
- When Brayan provides corrected grades or profile facts during an application-material task, update the canonical `profile/cv-master.md` first and any directly active tailored materials that depend on it.

## Related canonical skills

These are listed for discovery only, load the canonical skill directly by bare name when needed.

- `notes-intake-agent` — Anything Inbox capture routing, OCR/STT/URL context, and concise output rules.
- `inbox-triage-agent` — recurring inbox cleanup and transient-queue policy.
- `daily-review-agent` — daily priority review, daily-note update, and briefing format.
- `decision-reminders-agent` — pending-decision reminder behavior.
- `topic-recommendations-agent` — recurring recommendation balance and durable recommendation updates.
- `vault-structure-auditor-agent` — report-only Vault v2 structure audit behavior and approval boundaries.
- `opportunity-intake-agent` — opportunity-record creation/status/routing behavior.
- `opportunity-preparation-agent` — adaptive one-opportunity preparation behavior.
- `vault-workflow-migrations` — scoped migrations of vault workflows/templates/dashboards/skills/automation.

## Supporting references

Load these only when the task needs extra detail:

- `references/project-workspace-control-layer.md` — using vault project notes as control layers for external repos/experiments.
- `references/vault-capture-routing-workflows.md` — reusable capture-promotion patterns.
- `references/vault-repair-and-audit-workflows.md` — unusual repair, retest, and audit workflows.

## Vault GitHub tracking / backup workflow

Use this when initializing or maintaining git/GitHub tracking for `~/personal_vault`.

1. Orient first with `_meta/schema.md`, `_meta/index.md`, and `_meta/log.md`.
2. Check auth and repo state before changing anything:
   - `gh auth status`
   - `git status --short --branch`
   - `git remote -v`
3. Keep `.gitignore` conservative for editor/cache/secrets noise.
4. For broad vault-state commits, group the commit message around the origin of the changes: daily/recommendation automation, opportunity/application preparation, profile/CV corrections, audits, or manual vault maintenance. Prefer one clear vault commit over many tiny chronology commits when Brayan asks to commit the current state.
5. Run a basic pre-push scan for obvious private keys/token patterns; report it as a basic pattern scan, not proof of no secrets. If PDFs/binaries are included, explicitly say whether the scan skipped them.
6. If raw assets include personal documents, note that the private GitHub repo is the privacy boundary.
7. Record meaningful infrastructure changes in `_meta/log.md` before committing when possible.
8. Verify after push that the repo is private, remote points to `git@github.com:brayanb1701/personal-vault.git`, and branch tracks `origin/main` with a clean worktree.

## Pitfalls

- Do not overwrite raw source material.
- Do not treat OCR output as polished truth.
- Do not let inbox notes become permanent storage.
- Do not create isolated notes with no links unless unavoidable.
- Do not use `projects/` as a generic place for important files; separate true projects from workflows, guides, support assets, references, opportunities, and decisions.
- Do not reintroduce legacy split opportunity/application-packet paths; Vault v2 uses `opportunities/<slug>/opportunity.md` and `opportunities/<slug>/application/` only.
- Do not assume dirty git files/commits in the vault or Hermes personalization repo are mistakes: Brayan may have concurrent sessions editing the same repositories. Report exact paths and diffs clearly, then ask or scope commits to only the files intentionally changed.
- Do not leave completed migration/design analyses in active-looking meta paths where future agents may treat stale plans as current instructions; park them in `_meta/tmp_analysis/` or a clearly labeled archive.
- Do not let a general resource-planning fact contaminate an active project's execution context. If Brayan says a compute credit/budget/resource is for “general” or “other projects,” keep it out of unrelated active project prompts and files.
