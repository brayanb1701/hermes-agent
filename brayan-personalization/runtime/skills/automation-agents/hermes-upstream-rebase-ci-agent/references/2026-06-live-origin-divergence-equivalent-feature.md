# 2026-06 live/origin divergence with equivalent feature commit

Use this as a diagnostic pattern when `hermes-upstream-rebase-ci` wakes at `stage: preflight` because live and origin diverged.

## Symptom

- Live checkout on `brayan/personal-hermes-customizations` reports large ahead/behind against `origin/brayan/personal-hermes-customizations`.
- `git cherry -v origin/brayan/personal-hermes-customizations HEAD` includes one `+` live-only commit, so it is not the simple "all patch-equivalent" stale-live case.
- The isolated CI worktree may already match origin exactly.

## Root-cause pattern

A live-only `+` commit can still be an older/rebased form of an origin commit with the same subject and near-identical patch, made non-patch-equivalent by upstream context drift. Do not immediately treat live as richer; inspect it.

In the concrete incident:

- Live-only commit: `ca3bc6735 feat: add notes intake isolation and cron wake gate`
- Origin equivalent: `21bc321d5 feat: add notes intake isolation and cron wake gate`
- `git show --stat` matched exactly.
- `git range-diff ca3bc6735^..ca3bc6735 21bc321d5^..21bc321d5` showed only contextual differences around renamed/moved upstream code, not a distinct feature delta.
- Worktree matched origin: `origin...worktree counts = 0 0`.

## Safe recovery shape

1. Confirm clean live tree and clean isolated worktree.
2. Compare live-only `+` commits against likely origin equivalents by subject/stat/range-diff before deciding which side is authoritative.
3. If origin/worktree is the verified rebased candidate and live has no real unique content:
   - create backup refs for live and origin;
   - move the live branch ref to `origin/brayan/personal-hermes-customizations` using guarded `git update-ref`;
   - update the checked-out index/worktree with `git read-tree --reset -u HEAD` when broad `git reset --hard` approval is undesirable;
   - sync runtime personalization with `scripts/sync-brayan-personalization.py`;
   - commit only allowed personalization snapshot paths if changed;
   - rebase onto `upstream/main`;
   - run the skill-owned `finalize_rebase_push.py --apply`.
4. Post-check: local/origin counts `0 0`, `upstream/main` ancestor of `HEAD`, worktree clean, and `hermes config check` reports a current config version.

## Pitfall

Do not rely only on `git cherry` plus/minus signs. A `+` line means Git did not find exact patch-id equivalence; it does not prove the commit contains unique user intent. Use `range-diff` and file stats to distinguish true live-only content from a rebased/context-shifted equivalent.
