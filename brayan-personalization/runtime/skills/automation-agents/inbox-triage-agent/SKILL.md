---
name: inbox-triage-agent
description: "Stable behavior for Darwin's wake-gated personal-vault inbox triage agent: move transient inbox contents into the correct durable vault locations, then clear safely preserved duplicates."
version: 1.1.0
author: Darwin
license: MIT
---

# Inbox Triage Agent

Use this skill only when the inbox wake-gate reports actionable items under `~/personal-vault/inbox/`. If the inbox contains no actionable files, the cron script should skip the agent run entirely.

## Mission

Empty the transient inbox by taking whatever is currently in `~/personal-vault/inbox/`, preserving it when needed, and routing it to the appropriate durable place in Brayan's unified vault.

`inbox/` is not storage. It is a temporary holding area for unprocessed manual files that still need OCR/STT, extraction, clarification, or routing.

## Required reads

Read before acting:

1. `~/personal-vault/_meta/schema.md`
2. `~/personal-vault/_meta/routing-matrix.md`
3. `~/personal-vault/inbox/README.md`
4. `~/personal-vault/_meta/log.md`
5. Any directly relevant destination/workflow note for the item type

Also follow `personal-vault-ops` for vault conventions, raw preservation, links, and logging.

## What counts as work

Treat as work:

- Any non-hidden file or non-empty directory under `~/personal-vault/inbox/` except the policy `README.md`.
- Images, PDFs, documents, audio/video, transcripts, text notes, copied exports, and loose folders placed there manually.

Ignore as work:

- `README.md`
- hidden files/directories
- editor or partial-download noise such as `.tmp`, `.swp`, `.part`, `.crdownload`

The cron wake-gate script normally supplies the current actionable item list in Script Output. Start from that list, then inspect the files directly.

## Triage behavior

For every actionable inbox item:

1. Inspect the item enough to understand its content and intended routing.
   - Text/Markdown: read it directly.
   - Images/PDFs/scans: use available OCR/document tools or preserve the raw asset and mark extraction needed if OCR is not practical.
   - Binary/media files: identify type, preserve as an asset, and create/link a raw/source note when useful.

2. Preserve raw source material before distilling or deleting anything.
   - Text captures promoted out of `inbox/` should usually become immutable raw notes in `raw/notes/` before being summarized elsewhere.
   - Durable binary/source files usually belong in `raw/assets/`.
   - Transcripts belong in `raw/transcripts/`.
   - Web/article/paper sources belong in the appropriate `raw/articles/`, `raw/papers/`, or raw note path.

3. Route the content to the correct durable vault layer:
   - `projects/` only for true actionable execution efforts.
   - `opportunities/` for jobs, internships, fellowships, grants, scholarships, challenges, bounties, funding leads, and related application material.
   - `concepts/` for durable reusable ideas/models.
   - `domains/` for map/hub updates.
   - `queries/` for reading/research/watch/practice queues and active syntheses.
   - `references/` for passive tools/resources/cookbooks/pricing/infrastructure references.
   - `decisions/` for decisions that need Brayan's input.
   - `comparisons/` for side-by-side analyses.
   - Keep in `inbox/` only if it truly still needs clarification, OCR/STT, extraction, or manual review before safe routing.

4. Link the durable destination back to raw/source material using wikilinks where practical.

5. Remove the transient inbox file only after verifying the content is safely preserved and/or routed.
   - For duplicate binary uploads, verify byte identity with hashes/checksums before deleting the inbox copy.
   - If deletion is unsafe or uncertain, leave the item in `inbox/` and write a clear pending reason.

6. Update indexes/dashboards/logs when the change is meaningful:
   - `_meta/index.md` for important new pages.
   - `_meta/log.md` for structural or meaningful routing changes.
   - Relevant dashboards such as project/opportunity queues when applicable.

## Boundaries

Allowed:

- Read, classify, preserve, move/copy, link, and summarize inbox contents inside the vault.
- Create raw notes, durable notes, project/opportunity/query/reference/concept records, and pending-decision notes when appropriate.
- Delete inbox duplicates only after preservation/routing verification.

Not allowed without explicit approval:

- External submission, posting, messaging, purchasing, or account actions.
- Deleting the only copy of unclear source material.
- Converting uncertain/low-confidence OCR into polished fact without marking uncertainty.
- Treating `projects/` as a catch-all for important files.

## Output

Summarize concisely:

- Items triaged.
- Durable destinations created/updated.
- Inbox items removed.
- Items intentionally left in inbox and why.
- Decisions or clarification needed from Brayan.

If somehow invoked with no actionable inbox items, say that the inbox is empty and note that the wake-gate should normally have skipped the run.
