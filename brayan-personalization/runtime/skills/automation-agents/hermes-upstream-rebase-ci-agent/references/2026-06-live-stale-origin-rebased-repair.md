# Live stale, origin/worktree already rebased repair (2026-06-05)

Use this as a concrete pattern when `hermes-upstream-rebase-ci` wakes at `stage: preflight` because live `brayan/personal-hermes-customizations` and `origin/brayan/personal-hermes-customizations` diverged, but the isolated CI worktree is clean and matches origin.

## Observed shape

- Live checkout: on `brayan/personal-hermes-customizations`, clean, but `ahead 69, behind 245` against origin.
- Isolated worktree: clean, detached at the same commit as `origin/brayan/personal-hermes-customizations`.
- Cherry-pick-aware comparison:
  - live-only meaningful commits: `0`
  - origin-only meaningful commits: many upstream/rebased commits
- Conclusion: live was stale; origin/worktree was the richer candidate. Do not choose by recency alone, and do not reset blindly without backups.

## Repair pattern

1. Inspect without changing refs:
   - `git status --short --branch`
   - `git worktree list --porcelain`
   - `git rev-list --left-right --count origin/brayan/personal-hermes-customizations...brayan/personal-hermes-customizations`
   - `git log --left-only --cherry-pick --no-merges --oneline origin/...live`
   - `git log --right-only --cherry-pick --no-merges --oneline origin/...live`
2. Create backup refs for live, origin, and worktree heads under `refs/backup/hermes-upstream-ci/<timestamp>/...`.
3. In the isolated worktree, create a temporary repair branch from the clean origin-matching candidate.
4. Rebase that branch onto `upstream/main` with `GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true` and rerere enabled.
5. Run `scripts/sync-brayan-personalization.py`, commit only allowed `brayan-personalization/runtime/**` changes if present.
6. Run focused verification from the parent skill.
7. Move the live branch to the verified repair branch with `git update-ref`, not a broad destructive reset.
8. Run the skill-owned finalizer with `--apply`; do not bypass it with direct force-push.
9. After finalizer, fetch and confirm:
   - `origin...HEAD` count is `0 0`
   - `upstream/main` is an ancestor of `HEAD`
   - worktree is clean
   - `hermes config check` is current

## Config migration pitfall

A config check run before updating the live checkout can report the old schema as current. After the live branch moves onto newer upstream code, the finalizer or a fresh live `hermes config check` may report `Config version: N → N+1 (update available)`. Treat that as actionable even if the finalizer overall returned `ok: true`: run `hermes config migrate`, sync the migrated runtime config into `brayan-personalization/runtime/`, commit the snapshot, and rerun the finalizer.
