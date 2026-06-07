# Fetch-upstream transient DNS recovery (2026-06-06)

Use this pattern when the daily `hermes-upstream-rebase-ci` pre-run script wakes at `stage: fetch_upstream` with a DNS/network error such as `ssh: Could not resolve hostname github.com: Temporary failure in name resolution`.

## Observed shape

- Failure happened before any rebase or worktree mutation.
- Live checkout was clean on `brayan/personal-hermes-customizations`.
- After the transient network issue cleared, `git fetch upstream main` and `git fetch origin brayan/personal-hermes-customizations` succeeded.
- Rerunning the pre-run script completed the isolated rebase, tests, config check, and push.
- Because the script intentionally does not mutate the live checkout, live could be left behind origin after the successful rerun.

## Recovery pattern

1. Inspect the injected JSON/log first; confirm the failed stage is only `fetch_upstream` and no rebase is in progress.
2. Verify current network/fetch state with non-mutating probes:
   - `getent hosts github.com`
   - `git fetch upstream main --quiet`
   - `git fetch origin brayan/personal-hermes-customizations --quiet`
3. If fetches now succeed and both live/worktree are clean, rerun `/home/brayan/.hermes/scripts/hermes_upstream_rebase_ci.py` deliberately.
4. If the script emits `wakeAgent: false` with `status: updated`, inspect its JSON for verification results and pushed commit.
5. Compare live vs origin before moving live:
   - `git rev-list --left-right --count origin/brayan/personal-hermes-customizations...HEAD`
   - `git log --right-only --cherry-pick --no-merges --oneline origin/brayan/personal-hermes-customizations...HEAD`
   - proceed only when live-only meaningful commits are `0`.
6. Create backup refs for live/origin/worktree heads under `refs/backup/hermes-upstream-ci/<timestamp>/...`.
7. Move the live branch to the verified origin head with `git update-ref refs/heads/brayan/personal-hermes-customizations origin/brayan/personal-hermes-customizations`, then refresh the checked-out tree with `git checkout -f brayan/personal-hermes-customizations`.
8. Run the skill-owned finalizer with `--apply`. If it reports `stage: no_op` because origin already matches local HEAD, that is acceptable only if the rerun script and/or explicit post-checks already ran tests/config checks.
9. Run post-checks: `HEAD...origin` is `0 0`, upstream is an ancestor of `HEAD`, worktree is clean, `hermes config check` is current.
10. If the gateway is running, it may still be using old imported code until restart. In autonomous cron, a restart can be blocked by approval; do not bypass it. Report the manual restart command instead.

## Pitfalls

- Do not preserve the initial DNS error as a durable “GitHub unavailable” conclusion; the durable lesson is to retry fetch only after confirming repo state remained safe.
- Do not leave live stale after the isolated script successfully pushed origin. Compare cherry-pick-aware history and move live only when there are no live-only meaningful commits.
- Do not assume `finalize_rebase_push.py --apply` reruns tests in `no_op` mode; verify tests were already run by the script or run them explicitly before reporting success.
