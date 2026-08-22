# Project activation

Canonical vault workflow: `~/personal-vault/_meta/workflows/projects/project-activation-workflow.md`.

## Preconditions

- Brayan approval exists or the capture asks to start now.
- Objective, next action, success criteria, stop condition, priority, area, and slug are known.
- Workspace belongs under `/home/brayan/projects/<slug>/`.

## Procedure

1. Patch README frontmatter to `status: active` and set all active required fields.
2. Run `python3 ~/.hermes/scripts/project_scaffold.py --project /home/brayan/personal-vault/projects/<slug>/README.md --activate`.
3. Verify `PROJECT_STATUS.md` and `PROJECT_CHANGELOG.md` contain rendered values, not template placeholders.
4. Add/update `projects/dashboard.md`.
5. Remove `projects/backlog.md` seed row.
