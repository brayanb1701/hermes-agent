# Project workspace control files

Active projects execute under `/home/brayan/projects/<slug>/`.

## Required from activation

- `PROJECT_STATUS.md`: concise current snapshot an agent reads first after README.
- `PROJECT_CHANGELOG.md`: chronological parser-friendly state/change signal.

## Handoff files

- `PROJECT_CLOSEOUT.md`: workspace closeout input; preserved and marked complete/paused after processing.
- `PROJECT_REOPEN.md`: reopen/resume handoff; preserved and marked complete/paused after processing.

Do not infer project state from noisy git activity when these control files exist. Missing required control files for an active project is drift.
