# Vault Capture Routing Workflows

Reusable routing patterns for Brayan's personal vault. Load this only when a capture needs more detail than `personal-vault-ops` provides.

## General capture promotion

1. Orient with `_meta/schema.md`, `_meta/index.md`, `_meta/log.md`, and relevant hubs.
2. Preserve substantial original input as raw source under `raw/notes/`, `raw/assets/`, `raw/papers/`, or `raw/transcripts/` as appropriate.
3. Search for existing related notes before creating new durable notes.
4. Route to the correct layer:
   - `projects/` for true execution efforts.
   - `concepts/` for durable reusable ideas.
   - `queries/` for active reading/research/watch/practice queues.
   - `references/` for passive tools/resources/cookbooks.
   - `opportunities/` for jobs, internships, fellowships, grants, scholarships, challenges, bounties, and funding leads.
5. Link from relevant hubs and update `_meta/index.md` / `_meta/log.md` when structure changes.

## Text idea captures

Preserve original wording in `raw/notes/`, then distill into a concept, project, domain note, comparison, or queue. New seed projects should include objective, why it matters, MVP/experiment shape, open questions, next actions, sources, and links.

## Source / reading bundles

For bundles of articles, papers, X threads, videos, courses, or repos, preserve the original bundle in `raw/notes/`, then create/update a queue in `queries/`. Mark items pending unless Brayan says they were read/watched. Include priority, what to extract, and a suggested first path.

## Media watch queues

Keep learning-potential and fun/no-note-taking items separate. Do not turn every interesting video into homework. Fetch transcripts/summaries only when Brayan asks or the substantive content is central enough to justify it.

## Handwritten/document captures

Preserve the source image/document as a durable asset, preserve OCR/transcript text as raw evidence when useful, mark uncertain OCR lines, then distill to the durable destination.

## Foundational source bundles

For important folders/bundles, preserve a byte-identical raw copy, verify hashes, create a manifest raw note, then distill durable operating doctrine into `_meta/` or relevant hubs. Do not modify the preserved source bundle.

## Resource-planning captures

Expiring credits, coupons, cloud budgets, hardware availability, or temporary resources are usually portfolio-level planning notes under `queries/`, plus a pending decision/reminder if needed. Do not inject them into an active project unless Brayan explicitly makes them project-specific.
