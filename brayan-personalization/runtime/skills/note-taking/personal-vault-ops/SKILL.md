---
name: personal-vault-ops
description: Operate Brayan's unified personal vault at ~/personal_vault — a combined Obsidian vault and LLM wiki used by Darwin for capture, routing, linking, reviews, and project support.
version: 1.0.0
author: Darwin
license: MIT
---

# Personal Vault Ops

Use this skill whenever work touches Brayan's second brain, notes, wiki, inbox, project routing, topic recommendations, or vault maintenance.

## Vault location
- `~/personal_vault`

## Orientation order
At the start of any vault-related session, read:
1. `~/personal_vault/_meta/schema.md`
2. `~/personal_vault/_meta/index.md`
3. `~/personal_vault/_meta/log.md`
4. Any directly relevant domain/project notes

## Core principle
This is one unified system:
- Obsidian vault
- LLM wiki
- Darwin's operating memory substrate for structured knowledge

Do not split them mentally into separate systems unless the user asks.

## Folder roles
- `_meta/` — rules, architecture, index, log
- `inbox/` — quick capture and triage
- `raw/` — immutable source material and assets
- `concepts/` — durable concepts
- `projects/` — execution and active efforts
- `domains/` — navigation hubs by area
- `comparisons/` — side-by-side analyses
- `queries/` — saved synthesized answers
- `daily/` — reviews and snapshots

## Important hubs
- `domains/ai/ai-map.md`
- `domains/physics/physics-map.md`
- `domains/coding/coding-map.md`
- `domains/creative/creative-map.md`
- `domains/economy/economy-map.md`
- `domains/opportunities/opportunities-map.md`
- `projects/project-backlog.md`
- `projects/darwin-improvement.md`
- `queries/topic-recommendations.md`

## Filing rules
- Raw capture stays raw first
- For text captures that are being promoted out of `inbox/`, preserve the original wording as an immutable raw note in `raw/notes/` before distilling into a concept/project/domain note
- Unclear or still-processing items go to `inbox/`
- `inbox/` is transient triage, not durable storage
- Once an item is confidently routed into a durable destination, remove it from `inbox/` rather than keeping duplicate content there
- Durable knowledge goes to `concepts/`, `domains/`, `comparisons/`, or `queries/`
- Actionable execution goes to `projects/`
- Assistant-improvement ideas should usually link to `projects/darwin-improvement.md`
- Income, trading, and monetization ideas should usually link to `domains/economy/economy-map.md`
- Jobs, internships, fellowships, grants, and project funding leads should usually link to `domains/opportunities/opportunities-map.md`

## Maintenance rules
- Prefer `[[wikilinks]]
- Add important pages to `_meta/index.md`
- Append meaningful structural changes to `_meta/log.md`
- Keep domain notes as navigation hubs, not giant dumps
- Avoid polluting durable notes with low-confidence OCR output or raw scraps
- When removing duplicate binary uploads from `inbox/` after promotion to `raw/assets/`, verify byte identity first with hashes/checksums, then update any raw source note that points at the transient `inbox/` path so it preserves the original upload filename without depending on a deleted file path.
- When triaging `inbox/_captures/media-transcripts/`, keep only artifacts still needed for intermediate processing or explicitly referenced by a raw note; remove unlinked duplicate OCR/STT artifacts once the capture has been preserved in `raw/` and linked to a durable destination

## Current architecture docs
Read these when relevant:
- `~/personal_vault/_meta/ingestion-pipeline.md`
- `~/personal_vault/_meta/ocr-workflow.md`
- `~/personal_vault/_meta/review-cron-system.md`
- `~/personal_vault/_meta/vault-access-layer.md`
- `~/personal_vault/_meta/routing-matrix.md`
- `~/personal_vault/_meta/local-ai-stack.md`

## Current runtime helpers
- Telegram notes intake group: `Anything Inbox` (`chat_id: -1003960601334`)
- Enabled Hermes plugin: `notes_preprocessor`
- The notes group uses a Telegram `channel_prompt` plus a `pre_llm_call` plugin hook so captures are preprocessed into structured intake context before Darwin routes them into the vault.
- The live Anything Inbox config uses `notes_intake.auto_new_session_per_capture: true`: each new capture should run in a fresh gateway session by default to prevent unrelated notes/ideas/jobs from contaminating each other. If multiple URLs/fragments are related, Brayan should send them in the same Telegram message; one agent then handles that whole bundle together.
- The notes preprocessor supports multiple URL prefetches (currently capped at 10) and should treat multiple URLs in one message as potentially related before deciding whether to create one integrated note, several cross-linked notes, or a job/opportunity record plus supporting sources.
- Local OCR/STT packages are available to Hermes through a `.pth` link into `~/.hermes/venvs/ocr_test` (also aliased as `~/.hermes/venvs/ocr`).

## Live ingestion reality vs design docs
When auditing or explaining the notes intake pipeline, distinguish what is now live from what is still only a design goal:
- Live runtime: Telegram media is cached locally by the gateway before the agent turn.
- In `Anything Inbox` specifically, images now go through a dedicated pre-LLM notes-intake pipeline in `~/.hermes/hermes-agent/gateway/notes_intake.py`.
- That live image pipeline does `classify -> OCR-first for handwritten/document-like captures -> vision transcription fallback if OCR is weak -> compact summary for screenshots/diagrams/mixed visuals -> inject text block into the user message`.
- Voice/audio in `Anything Inbox` is transcribed before the agent reasons over it, and the transcript is also persisted as a temporary artifact under `~/personal_vault/inbox/_captures/media-transcripts/`.
- The `notes_preprocessor` plugin is still text-first, but it is now intentionally minimal: it annotates modality, preserves media-analysis blocks, and prefetched URL context when possible.
- It no longer emits regex-based intent labels or suggested vault targets; final organization is left to the agent.
- Retrieval of broader related context is still the agent's job, not the preprocessor's.
- The live notes-intake pipeline on this machine currently uses the main provider for image classification / vision OCR fallback (`notes_intake.vision_provider: main`, `notes_intake.vision_model: gpt-5.4-mini`).
- Earlier Copilot-preferred routing was retired from the live config after retesting showed Copilot vision was unreliable here: `gpt-5.4-mini` is unsupported for Copilot vision requests, and `gpt-4.1` may return `Access to this endpoint is forbidden` for notes-intake image calls.
- The notes-intake helper now records the actual effective provider/model and fallback error in injected media blocks and transcript artifact metadata.
- Related-topic suggestion and grouping of adjacent project ideas are still not a guaranteed automatic pre-response step; those remain downstream agent/review behaviors rather than preprocessing guarantees.

## Current classification layers for Anything Inbox
When the user asks how the pipeline decides "what kind of thing this is," separate the layers clearly instead of describing one blended classifier:

1. Gateway media-type branching
   - `gateway/run.py` first branches on transport/media type: image vs audio vs document vs plain text.
   - Only `Anything Inbox` images use the dedicated notes-intake image pipeline; other images fall back to generic vision enrichment.
   - Audio uses STT/transcript persistence; generic documents currently have much lighter handling than images/audio.

2. Image-content classification
   - `gateway/notes_intake.py` uses a vision model to classify images into `handwritten_note`, `document_scan`, `screenshot`, `diagram`, `photo`, `mixed`, or `other`.
   - This layer decides whether to run OCR, summary, or both.
   - This is the layer that recognizes a handwritten note should be OCR'd.

3. Text-first preprocessor context
   - After OCR/STT/summary injection, `notes_preprocessor` still classifies the resulting message as `media`, `link`, `text`, or `media-or-empty`.
   - It may also prefetch URL content and inject a compact title/description/text excerpt when direct fetch succeeds.
   - It no longer emits regex-based intent labels or suggested vault targets; the agent decides final organization.

Important consequence:
- "handwritten note" is still answered by the image classifier layer.
- Final vault routing is now intentionally an agent decision rather than a preprocessor regex decision.
- When auditing behavior, report both the image-kind decision and what preprocessed text/URL context the agent actually received.

## Recommended behavior
When working with the vault:
1. orient
2. preserve raw input
3. classify intent
4. route to the correct note layer
5. add links
6. update index/log if the structure changed

## Vault GitHub tracking / backup workflow
Use this when initializing or maintaining git/GitHub tracking for `~/personal_vault`.

1. Orient first by reading `_meta/schema.md`, `_meta/index.md`, and `_meta/log.md` so repository changes respect vault conventions.
2. Check GitHub auth and current repository state before making changes:
   - `gh auth status`
   - from `~/personal_vault`: `git status --short --branch`, `git remote -v`, and `gh repo view brayanb1701/personal-vault --json nameWithOwner,visibility,isPrivate,sshUrl,url,defaultBranchRef` when a remote may already exist.
3. Before the first push, add or verify a conservative `.gitignore` for local-only/editor/cache/secrets noise:
   - `.DS_Store`, swap files, backups
   - `.obsidian/workspace.json`, `.obsidian/workspace-mobile.json`, `.obsidian/cache/`, `.obsidian/plugins/*/data.json`
   - `.env`, `.env.*`, `.cache/`, `__pycache__/`, generated temp files
   - large generated media such as `*.mp4`, `*.wav`, `*.mp3` unless intentionally preserved
4. Run a basic pre-push safety scan for obvious private keys and common token patterns. Do not claim this proves absence of secrets; report it as a basic pattern scan.
5. Check repository size and large files before pushing. If raw assets include personal documents such as CV PDFs/DOCX files, explicitly note that the private GitHub repo becomes the privacy boundary rather than silently excluding durable raw assets.
6. Initialize and push with `gh` when available:
   - `git init -b main`
   - `git add .`
   - `git commit -m "Initial personal vault snapshot"`
   - `gh repo create personal-vault --private --description "Private Obsidian/LLM personal vault" --source . --remote origin --push`
7. Record meaningful infrastructure changes in `_meta/log.md` before committing when possible.
8. Verify after push:
   - `git status --short --branch` is clean and tracking `origin/main`
   - `git remote -v` points to `git@github.com:brayanb1701/personal-vault.git`
   - `gh repo view ...` reports `visibility: PRIVATE`, `isPrivate: true`, and default branch `main`

## Schema/orientation file repair workflow
Use this if an orientation file such as `_meta/schema.md` appears corrupted, empty, or contains a literal tool/cache status string instead of real vault content.

1. Verify the problem from disk, not only from a cached `read_file` response. Use a terminal/Python read or file-size check if `read_file` returns a suspicious message like `File unchanged since last read...`.
2. Search session history and nearby vault docs for the intended schema details before rewriting:
   - `session_search` for `_meta/schema.md`, `Vault Schema`, `folder roles`, `frontmatter`, and `type: inbox`.
   - Existing docs such as `_meta/routing-matrix.md`, `_meta/index.md`, `_meta/review-cron-system.md`, and representative notes with frontmatter.
3. Reconstruct the schema conservatively from stable conventions already used in the vault: folder roles, standard frontmatter, note type conventions, inbox policy, raw preservation rules, linking rules, and core hub links.
4. Restore the schema note, add it to `_meta/index.md` if missing, and append a `_meta/log.md` entry explaining the repair.
5. Re-read the repaired file, index, log, and inbox inventory to verify the vault is clean and the orientation path works again.

## Text idea capture promotion workflow
Use this when Brayan sends a substantial text idea to `Anything Inbox` and it is clearly worth preserving as more than a transient inbox item.

1. Orient by reading `_meta/schema.md`, `_meta/index.md`, `_meta/log.md`, and the directly relevant domain/project hubs.
2. Search the vault for existing matching notes before creating anything new, so adjacent ideas are merged or linked instead of duplicated.
3. Preserve the user's original wording verbatim in a raw source note under `raw/notes/` with source chat, modality, captured date/time when available, tags, and routing notes.
4. Distill the idea into the right durable layer:
   - `projects/` for actionable builds, systems, products, experiments, or multi-step implementations.
   - `concepts/` for reusable ideas without immediate execution structure.
   - `domains/`, `comparisons/`, or `queries/` only when the capture is primarily navigation, analysis, or synthesis.
5. For a new seed project, include: core idea, why it matters, current design sketch, open research questions, MVP proposal, next actions, sources, and linked notes.
6. Link the durable note from relevant domain hubs and `projects/project-backlog.md`; add important active projects to `_meta/index.md`.
7. Append a concise routing record to `_meta/log.md` and verify with a search for the new slug/title.

## Pending reading-list / research-source queue workflow
Use this when Brayan sends a bundle of articles, blogs, papers, X threads, videos, or other sources that he has not read yet and wants saved for later prioritization/extraction.

1. Orient by reading `_meta/schema.md`, `_meta/index.md`, `_meta/log.md`, and the directly relevant domain/project hubs.
2. Preserve Brayan's original bundle verbatim in `raw/notes/` as a source capture, including his comments next to each URL/file.
3. Search the vault for existing reading queues, source notes, or related concepts before creating duplicates.
4. Create or update a durable queue note, usually in `queries/`, with:
   - every item marked `pending` unless Brayan explicitly says it was read/watched;
   - a priority tier such as P0/P1/P2 based on current goals, not just apparent source quality;
   - a short `what to extract` field for each item;
   - for educational videos, a `learning mode` field when useful (e.g. calm conceptual watching, active code replication, research/idea extraction, foundation refresher);
   - for code-heavy learning videos, explicitly prefer active replication over passive viewing and note when the source should later become a small project/notebook/repo;
   - a suggested first reading/watching path;
   - a reusable extraction template for Brayan's key takeaways, Darwin synthesis, follow-up actions, deeper links/papers, generated artifacts, and related vault connections.
5. If one source exists as a transient inbox file because a website/social platform was inaccessible, promote that file to `raw/articles/` or `raw/papers/`, link it from the queue, and remove the transient inbox duplicate after preservation.
6. For dynamic or blocked pages, inspect with browser tools if lightweight fetching fails; if still blocked, record the access issue in the queue rather than inventing content.
7. Link the queue from relevant domain hubs and active projects, especially `domains/ai/ai-map.md`, `projects/darwin-improvement.md`, and `projects/darwin-token-efficiency-and-local-model-training.md` when the sources affect AI, agents, token efficiency, or local/post-training.
8. Add important queues to `_meta/index.md`, append a structural entry to `_meta/log.md`, and verify by searching for the queue slug plus any removed inbox filename.

## Foundational source-bundle promotion workflow
Use this when Brayan drops a high-importance folder/bundle into `inbox/` that contains original sources plus derived principles/playbooks/specs that should become durable operating doctrine, especially for Darwin/Hermes, agentic coding, vault architecture, or long-term workflows.

1. Orient by reading `_meta/schema.md`, `_meta/index.md`, `_meta/log.md`, and directly relevant hubs/projects such as `domains/ai/ai-map.md`, `domains/coding/coding-map.md`, and `projects/darwin-improvement.md`.
2. Inventory the entire folder before editing anything. Capture filenames, subfolder roles, rough sizes/line counts, and headings so you understand which files are originals vs derived doctrine.
3. Preserve the full folder as an immutable raw source bundle under `raw/assets/YYYY-MM-DD-<bundle-slug>/` using a byte-preserving copy. Do not rewrite or normalize filenames inside the raw copy.
4. Verify preservation with per-file hashes against the inbox source. Record file count, hash match status, and any missing/extra files.
5. Create a raw source manifest under `raw/notes/YYYY-MM-DD-<bundle-slug>-manifest.md` that documents:
   - original transient inbox path
   - durable raw asset path
   - folder structure and intended semantics
   - preserved file inventory / source descriptions
   - derived notes created from the bundle
   - whether the original inbox copy was removed or intentionally left in place
6. Distill into durable `_meta/` notes when the bundle defines operating rules, architecture, or assistant behavior. Prefer a layered structure:
   - master hub note
   - stable principles/invariants note
   - evolving playbooks/workflows note
   - alignment/mismatch/adaptation note comparing the bundle against current Darwin/Hermes defaults
7. If Brayan gives a correction or desired adaptation, incorporate it into the derived notes rather than modifying the preserved sources. Example: for low-risk personal tools/prototypes, Brayan wants higher agent autonomy and looser review gates; encode that as a risk-tiered autonomy policy while keeping stricter review for external/irreversible/high-risk work.
8. Link the new foundation from relevant hubs (`_meta/index`, domain maps, active projects) and append a `_meta/log.md` entry.
9. Decide inbox cleanup based on user intent. Normally routed duplicates should be removed, but if Brayan explicitly says to avoid modifying the files or the source bundle is especially important, leave the inbox copy in place after hash-verified preservation and report that it is safe for manual removal.
10. Verify by rereading key notes, searching for the new slug/links, and confirming hash equality between inbox and raw bundle.

## Handwritten-note promotion workflow
Use this when an `Anything Inbox` image is clearly a handwritten note and the content is worth preserving beyond transient OCR.

1. Preserve the source image as a durable asset in `raw/assets/` with a descriptive date-prefixed filename.
2. Create a raw source note in `raw/notes/` that includes:
   - source chat / modality
   - original media cache path
   - durable asset wikilink
   - classification kind / OCR engine when available
   - the user's own context sentence if provided
   - the OCR transcript preserved as raw text
   - an explicit note when any OCR line looks uncertain
3. Distill the note into a durable destination, usually a `concepts/` note unless it is clearly a project/action item.
4. Link the durable note from the most relevant domain hub and, if needed, expand that hub's thread list to reflect the new topic.
5. Append a concise routing record to `_meta/log.md`.
6. After the raw note and durable note exist, remove the transient OCR artifact from `inbox/_captures/media-transcripts/` if it is no longer needed, so the inbox capture folder remains an intermediate queue rather than duplicate long-term storage.

This workflow is especially useful for handwritten reflections from videos, books, classes, or whiteboards where the OCR text is valuable but should not remain the only preserved representation.

## Retest reset / cleanup workflow
Use this when the user wants to repeat an ingestion test from a clean slate and avoid confusion with artifacts from a prior attempt.

1. Orient first by reading:
   - `~/personal_vault/_meta/schema.md`
   - `~/personal_vault/_meta/index.md`
   - `~/personal_vault/_meta/log.md`
   - any relevant pipeline docs such as `ingestion-pipeline.md` or `ocr-workflow.md`
2. Inventory the exact identifiers tied to the prior attempt before deleting anything:
   - note slug/title
   - raw asset filename
   - transcript filename
   - image cache IDs
   - session IDs / cron run IDs if directly tied to the test
3. Search both the vault and Hermes state for those identifiers so you distinguish:
   - functional artifacts that should be deleted for a clean retest
   - collateral references in maps/hubs that should be cleaned
   - historical audit/session traces that may remain and should be reported explicitly rather than silently ignored
4. Delete the concrete test artifacts first:
   - raw assets in `raw/assets/`
   - promoted notes in `concepts/`, `projects/`, etc. when they were created solely by the failed test
   - temporary transcripts in `inbox/_captures/media-transcripts/`
   - related cache files under `~/.hermes/image_cache/` when they belong to that exact test
   - directly associated session/cron output files only when the user clearly wants aggressive cleanup and the files are not needed for active continuity
5. Clean secondary vault references after deletion:
   - domain maps
   - indexes/hubs
   - logs only if they now point to removed artifacts and would create confusion
6. Re-search to verify the vault is clean for the target identifiers.
7. If any traces remain in Hermes session history or current conversation state, call them out explicitly as audit/history residue rather than treating them as active vault artifacts.
8. For handoff-quality work, create a `_meta/` document that states:
   - purpose of the retest
   - exact system under test
   - checklist of what to verify end-to-end
   - evidence another agent should capture
   - known failure modes from the previous attempt
   Then add the handoff note to `_meta/index.md`.

## Retest verification / audit workflow
Use this when the user asks whether a prior `Anything Inbox` handwritten-note run actually worked, especially if a session was deleted or the original transcript is no longer directly available.

1. Read the handoff / architecture docs first:
   - `~/personal_vault/_meta/anything-inbox-handwritten-note-retest-handoff.md` if present
   - `~/personal_vault/_meta/ingestion-pipeline.md`
   - `~/personal_vault/_meta/ocr-workflow.md`
   If the handoff file is missing, explicitly note that, search `_meta/` for similarly named handoff/retest docs, and continue the audit from logs + vault evidence instead of failing the workflow.
2. Pull live evidence from Hermes logs, not just the vault result:
   - `~/.hermes/logs/agent.log` for cache, provider, OCR, and fallback lines
   - `~/.hermes/logs/notes_preprocessor.jsonl` for modality, injected `[NOTES INBOX MEDIA ANALYSIS]`, and target routing
   - `~/.hermes/sessions/` when the logs are too sparse; the persisted session JSON often preserves the exact injected user message block, including `classification_engine`, `ocr_engine`, `ocr_fallback_used`, `ocr_local_engines_tried`, and transcript-path metadata even after temporary transcript artifacts have been cleaned up
3. Search the vault for the concrete identifiers tied to the run:
   - cached image id like `img_<hash>`
   - note slug/title
   - transcript artifact path
4. If the original session may be deleted or not in current context, use `session_search` with OR-joined identifiers/topic words to recover what the agent did after preprocessing.
5. Distinguish three layers in the verdict:
   - pipeline correctness (did OCR-first / preferred provider actually work?)
   - fallback correctness (did the system still succeed via fallback?)
   - vault-routing correctness (were raw note, durable asset, hub links, and cleanup handled correctly?)
6. Report both the intended path and the actual runtime path. For handwritten-image audits, explicitly check for:
   - local OCR attempted vs failed
   - Copilot preferred provider attempted vs failed
   - fallback to auxiliary/main provider
   - artifact metadata mismatches such as `ocr_engine` claiming one provider while logs show another
   - whether a bare `Vision auto-detect` line in `agent.log` actually corresponds to notes-intake fallback, or is merely auxiliary/client initialization; do not treat that line alone as proof that image classification or OCR used remote vision when session metadata shows `classification_engine: local_clip` and `ocr_fallback_used: false`
7. Use verdict language that separates user-visible success from architectural success. Example: "worked operationally via fallback, but not as designed."

## Pitfalls
- Do not overwrite raw source material
- Do not treat OCR output as polished truth
- Do not let inbox notes become permanent storage
- Do not create isolated notes with no links unless unavoidable
- Do not claim a test was "fully erased" if references still exist in active Hermes session history; distinguish practical retest cleanliness from total historical erasure
- Do not infer the real OCR/provider path from the final note alone; verify against logs
