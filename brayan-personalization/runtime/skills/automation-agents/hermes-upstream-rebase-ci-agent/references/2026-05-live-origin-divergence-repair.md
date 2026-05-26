# Live/origin personalization divergence repair (2026-05-21)

Use this reference when the wake-gate script stops at `stage: preflight` with a message like:

> Live brayan/personal-hermes-customizations and origin/brayan/personal-hermes-customizations have diverged. Refusing to choose a base automatically.

## Root cause pattern

The pre-run script intentionally refuses to choose between local live `brayan/personal-hermes-customizations` and `origin/brayan/personal-hermes-customizations` when neither is ancestor of the other. In the observed case:

- live checkout held older local CI-recovery/source-customization commits,
- origin held a newer pushed guard/test commit,
- the isolated CI worktree already contained a newer rebased candidate,
- source-only diff from origin to the worktree was tiny, while personalization/runtime diff was large and expected.

## Safe repair sequence

1. Inspect live, origin, upstream, and isolated worktree state before changing refs:
   - `git status --short --branch`
   - `git worktree list --porcelain`
   - `git rev-list --left-right --count origin/brayan/personal-hermes-customizations...brayan/personal-hermes-customizations`
   - compare the isolated worktree against origin with `git diff --stat origin/...HEAD -- ':(exclude)brayan-personalization'`.
2. Create non-destructive backup refs for live, origin, and the isolated worktree candidate before any branch surgery.
3. If the isolated worktree is clean and appears to be the richer/newer repair candidate, create a temporary repair branch there instead of editing the live checkout directly.
4. Reconcile small source-only origin deltas into that repair branch when they are clearly missing guard/test changes; keep large `brayan-personalization/runtime/**` differences as runtime snapshot churn unless evidence says otherwise.
5. Rebase the repair branch onto `upstream/main` with `GIT_EDITOR=true GIT_SEQUENCE_EDITOR=true`.
6. Run `scripts/sync-brayan-personalization.py` from the repair branch, commit only allowed personalization paths if changed, and verify a clean tree.
7. Run the focused verification commands from the parent skill.
8. Update the live `brayan/personal-hermes-customizations` branch to the verified repair candidate without a destructive broad reset. A safe pattern is:

   ```bash
   git switch --detach HEAD
   git update-ref refs/heads/brayan/personal-hermes-customizations <verified-repair-branch>
   git switch brayan/personal-hermes-customizations
   ```

9. Run the skill-owned finalizer with `--apply`; do not bypass it with direct `git push --force-with-lease` from the agent.
10. Final sanity check: local and origin match, `upstream/main` is an ancestor of HEAD, and the worktree is clean.
11. If the finalizer or post-finalizer `hermes config check` reports a config schema update (for example `23 → 24`), run `hermes config migrate` in the live checkout/runtime, verify `Config version: N ✓`, then run `scripts/sync-brayan-personalization.py`, commit only the resulting allowed `brayan-personalization/runtime/**` snapshot changes, and rerun the finalizer with `--apply`. This keeps the fork branch reproducible with the migrated runtime config; never resolve this by hand-editing `_config_version`.

## Notes

- The finalizer's pre-push snapshot may still show ahead/behind counts from before the final push/fetch; always do a post-finalizer sanity check if the report matters.
- Keep backup refs until Brayan has no need to recover the old live/origin/worktree heads.
