# Privacy and provenance audit

Scope: files added under `portable-hackathon/` on branch `brayan/hackathon-portable-skills`.

## Branch boundary

- Base: official `upstream/main` commit `40643cbaf9b767af146694131ffb8f8160f25e1c`.
- The branch does not descend from `brayan/personal-hermes-customizations` or `second-computer-evolution`.
- No live runtime snapshot or personal repository content is included.

## Explicit exclusions

The portable bundle contains none of the following:

- `.env`, `auth.json`, credentials, tokens, SSH keys, or connection strings;
- memories, user profile, vault notes, sessions, logs, cron jobs, agents, plugins, or channel configuration;
- chat/channel/user IDs, phone numbers, home or work address, employer details, private financial values, application history, or private project records;
- machine-specific `/home/...` paths.

Brayan's first name and ordinary Git author metadata are allowed by the owner's instruction.

## Scan results

Pre-push content scans covered:

- common API/token/private-key shapes;
- long numeric identifiers and phone-like strings;
- machine-specific absolute paths;
- private messaging/channel labels;
- user handles and common personal-data labels.

Findings were limited to non-personal documentation/examples:

- public DSPy and Outlines Discord community links;
- fictional phone/address/email examples in Outlines documentation;
- public repository commit hashes and sample Polymarket timestamps;
- generic privacy words in this audit and README;
- generalized document/CV workflows that contain no source identifiers or source-specific financial values.

No secret scanner executable was present, so this is a targeted pattern/content audit rather than a claim of formal secret-scanner coverage.

## Provenance

- Twenty-one selected skills are referenced from the official Hermes source tree at the branch base.
- Six vendored MIT skills are either former Hermes bundled skills or user-authorized Darwin-authored skills. Their provenance is recorded in `skills-manifest.json`.
- `webapp-testing` is from `anthropics/skills` commit `98669c11ca63e9c81c11501e1437e5c47b556621`; its Apache-2.0 `LICENSE.txt` is retained.
- Every vendored file is recorded in `VENDORED_SHA256SUMS`.

## Verification

The installer was compiled, dry-run, and applied against a disposable empty Hermes home. It installed exactly 28 unique `SKILL.md` files. No third-party package was installed as part of this branch preparation.
