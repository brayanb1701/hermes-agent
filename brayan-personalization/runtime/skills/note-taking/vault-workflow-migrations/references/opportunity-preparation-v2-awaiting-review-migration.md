# Opportunity preparation v2: awaiting-review migration case

Session pattern captured from migrating active opportunity records into Brayan's generalized opportunity/preparation workflow.

## Scope used

- Included: `opportunities/*/opportunity.md` with `status: awaiting-review`.
- Excluded by request: `2026-04-23-openai-parameter-golf-challenge`.
- Dashboard metadata was still allowed for the excluded record when explicitly requested.

## Records migrated

- `2026-04-23-constellation-astra-fellowship` -> `opportunity_kind: fellowship`, `workflow_mode: cv-tailoring`, `cv_relevance: required`.
- `2026-04-23-human-technopole-research-software-engineer` -> `opportunity_kind: job`, `workflow_mode: cv-tailoring`, `cv_relevance: required`.
- `2026-04-23-iaea-ai-ml-text-analytics-internship` -> `opportunity_kind: internship`, `workflow_mode: cv-tailoring`, `cv_relevance: strategic`.
- `2026-04-23-iaea-data-management-analytics-internship` -> `opportunity_kind: internship`, `workflow_mode: cv-tailoring`, `cv_relevance: strategic`.
- `2026-04-23-list-junior-rt-engineer` -> `opportunity_kind: job`, `workflow_mode: cv-tailoring`, `cv_relevance: required`.
- `2026-04-23-perplexity-ai-research-residency` -> `opportunity_kind: residency`, `workflow_mode: cv-tailoring`, `cv_relevance: required`.
- `2026-04-28-xiaomi-mimo-100t-token-grant` -> `opportunity_kind: grant`, `workflow_mode: application-draft`, `cv_relevance: irrelevant`.

All seven stayed `status: awaiting-review` with `automation_route: none` because existing work was sufficient for Brayan's manual review.

## File/field changes

- `tailoring_packet` -> `preparation_packet`.
- `application/tailoring-packet.md` -> `application/preparation-packet.md` for included records.
- Stale packet wording was cleaned, while valid `workflow_mode: cv-tailoring` was preserved.
- Xiaomi used a lightweight `preparation-packet.md` pointing to its existing `application-draft.md` rather than duplicating content.

## Validation evidence to reproduce

- `git diff --check` in vault and Hermes personalization repo.
- `python3 -m py_compile ~/.hermes/scripts/opportunity_preparation_ready_scan.py`.
- `python3 ~/.hermes/scripts/opportunity_preparation_ready_scan.py --dry-run` expected `selected_count: 0` for migrated awaiting-review records using `automation_route: none`.
- Search migrated folders for retired strings: `tailoring_packet`, `tailoring-packet`, `tailoring-ready`, `job-tailoring`, stale `Tailoring Packet` headings.
- Dashboard should have one populated `Kind` column and preserve priority order.
