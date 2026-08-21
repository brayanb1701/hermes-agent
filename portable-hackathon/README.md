# Portable hackathon skill profile

This private branch is a clean, work-computer-safe Hermes baseline for Brayan's hackathon work.

It is based directly on official `upstream/main` and does not inherit the personal runtime branch. It contains no runtime configuration, memories, vault data, cron jobs, channel identifiers, sessions, logs, credentials, or personal project records.

## What is included

`skills-manifest.json` selects 28 phase-relevant skills:

- 10 product/domain skills
- 12 build, orchestration, and assurance skills
- 6 creative, interface, and demo skills

Twenty-one are already present in the upstream Hermes source tree. Seven are vendored under `vendor-skills/` with license and provenance recorded in the manifest.

Approach-specific methodology packs are deliberately absent. Each bakeoff approach must keep its own pack local and pinned. Do not install or flatten those packs globally.

## Recommended setup on another computer

1. Install or clone Hermes from this branch.
2. Create a dedicated clean profile so unrelated personal skills are not mixed in:

```bash
hermes profile create hackathon
hermes profile show hackathon
```

3. Find that profile's Hermes home, then dry-run the installer:

```bash
python portable-hackathon/scripts/install-skills.py \
  --hermes-home ~/.hermes/profiles/hackathon
```

4. Apply after inspecting the exact 28-skill plan:

```bash
python portable-hackathon/scripts/install-skills.py \
  --hermes-home ~/.hermes/profiles/hackathon \
  --apply
```

5. Add provider credentials locally with `hermes auth`; never commit them.
6. Validate the profile:

```bash
hermes --profile hackathon config check
hermes --profile hackathon skills list
```

The installer only replaces skills with the same selected names and backs those versions up. It does not delete unrelated skills. Use a fresh profile when the goal is exactly this curated local set.

## Activation policy

Do not preload all 28 skills into every session. Activate the smallest phase-specific subset:

- Hiring Intake Firewall domain spike: `ocr-and-documents`, `document-digitization-audit`, `docx`, `pdf`, `outlines`
- Implementation: the approach-local methodology plus selected planning/TDD/debugging skills
- Assurance: `webapp-testing`, `dogfood`, `requesting-code-review`
- Demo package: `popular-web-designs`, `architecture-diagram`, `baoyu-infographic`, `powerpoint`

## Dependency and supply-chain policy

The branch installs skill instructions, not third-party Python or Node packages. Before adding a package during a project:

- confirm the official package/repository and maintainer;
- inspect release recency, ownership changes, install scripts, lockfile impact, and known advisories;
- pin versions and preserve the lockfile;
- run the applicable package audit and Hermes security audit;
- prefer standard-library or existing locked dependencies when practical.

## Privacy boundary

Allowed identity: Brayan's name and Git author metadata. Excluded: addresses, phone numbers, private chat or channel identifiers, employer details, vault content, application history, financial data, credentials, and machine-specific absolute paths.

`PRIVACY_AUDIT.md` records the pre-push checks performed for this branch.
