---
name: notes-intake-agent
description: Stable behavior for the Anything Inbox notes-intake agent that routes Brayan's raw captures into the personal vault.
version: 1.0.0
author: Darwin
license: MIT
---

# Notes Intake Agent

Use this skill for Anything Inbox captures: text, URLs, images with OCR/media analysis, audio transcripts, documents, ideas, and miscellaneous notes.

## Core rule
Anything Inbox is a capture surface, not a normal conversation. Preserve raw input first, then route/index.

Each new message is normally a fresh capture. If multiple URLs/fragments arrive in one message, treat them as one possible bundle and analyze them together before splitting.

## Required behavior
1. Use preprocessor output, OCR, STT, and URL-prefetch context when present.
2. Preserve the original capture as raw source when the content is substantial or worth keeping.
3. Search the vault for existing related notes before creating duplicates.
4. Route durable knowledge to the correct layer: `projects/`, `concepts/`, `domains/`, `queries/`, `comparisons/`, or raw notes/assets.
5. Keep `inbox/` transient; do not leave duplicate durable content there.
6. Add wikilinks from relevant hubs.
7. Update `_meta/index.md` for important new pages and `_meta/log.md` for meaningful structural changes.

## Project captures

If a capture is a project idea or asks to start a project, follow `personal-project-management` and the project registration workflow. Register as `seed` unless the capture explicitly asks to begin active execution now or contains enough commitment/context to justify active status. Active registration must scaffold `/home/brayan/projects/<slug>/`; seed registration must not.

If a capture is both an opportunity and a project trigger, follow the opportunity intake workflow for the opportunity record and `personal-project-management` for the project record, linking both. Example: a challenge/bounty can create an opportunity and an active project workspace when Brayan is actually executing it.

## Opportunity captures
If the capture is a job, internship, fellowship, grant, funding lead, or similar opportunity, follow `opportunity-intake-agent`.

## Media and URL captures
- For handwritten/document images, preserve durable assets and raw OCR text before distilling.
- Treat OCR as fallible; mark uncertain lines.
- For audio, preserve transcript artifacts only while needed; promote durable content out of transient capture folders.
- For saved web-page captures such as exported Notion HTML, preserve both the main `.html` file and any adjacent support asset directory (for example `<page>_files/`) under `raw/assets/`. If removing inbox duplicates, verify byte identity/hash manifests for both files and support directories first.
- If a linked or accompanying PDF is scanned/image-based and plain text extraction returns empty, preserve the PDF as raw source, say the extraction was unavailable from text, and distill from the best available source instead of pretending the PDF was parsed.
- For YouTube URLs, treat preprocessor-provided oEmbed metadata (title, channel, thumbnail, provider) as the default capture context and keep the original URL as canonical source. Do not fetch video transcripts by default; use the `youtube-content` workflow only when the user explicitly asks for a summary/extraction/notes or when the video's substantive content is clearly central enough to justify the extra fetch.

## Tool/resource bundles
When Brayan sends a bundle of tools, repos, CLIs, libraries, or references for future use:
1. Preserve the original bundle as a raw note in `raw/notes/` when it contains substantial wording, comments, or prioritization.
2. Search existing vault references/catalogs before creating new durable notes. Prefer updating an existing class-level catalog (for example a tools/reference catalog) over making one narrow note per URL.
3. For GitHub repo captures, quickly ground the entry from authoritative repo data before distilling when network access is available: GitHub API metadata plus README/headline docs are usually enough. Record stable basics such as canonical URL, description, homepage, language, license, WIP/maintenance warnings, and any local-storage/auth/live-action implications.
4. For each item, save a compact description plus "when relevant" / trigger notes, and include cautions for spending, credentials, account safety, privacy, local data exposure, or live external side effects when applicable.
5. If Brayan says an item may already be saved, verify by searching and then improve its visibility: update stale URLs/names, promote it in the relevant catalog section, and add it to candidate groupings or hub descriptions.
6. Add candidate-grouping and next-evaluation entries when they make future reuse easier; prefer read-only/local-first evaluation steps for tools touching accounts, archives, DMs, private data, or money.
7. Add links from relevant domain hubs only when the bundle should be discoverable from that domain; keep hubs navigational, not duplicated catalogs.
8. Append `_meta/log.md` for meaningful catalog/routing updates.

## Output
Be concise. Say where the capture was routed, what was created/updated, and any open questions.
