# Project workspace control files

Active projects execute under `/home/brayan/projects/<slug>/`.

## Required from activation

- `PROJECT_STATUS.md`: concise current snapshot an agent reads first after README.
- `PROJECT_CHANGELOG.md`: chronological parser-friendly state/change signal.

## Handoff files

- `PROJECT_CLOSEOUT.md`: workspace closeout input; preserved and marked complete/paused after processing.
- `PROJECT_REOPEN.md`: reopen/resume handoff; preserved and marked complete/paused after processing.

Do not infer project state from noisy git activity when these control files exist. Missing required control files for an active project is drift.

## Scaffold fallback

`project_scaffold.py --activate` depends on vault templates named `project-workspace-status-template.md` and `project-workspace-changelog-template.md`. If either template is missing, treat the helper run as failed even when it created the workspace directory: create the two required control files manually from the project README's canonical fields, verify that no placeholders remain, and report the missing-template infrastructure drift. Do not claim the scaffold completed successfully merely because its process exit code is zero; inspect its JSON `errors` array.
