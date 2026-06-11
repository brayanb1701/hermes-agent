# 2026-06 AGENTS.md upstream-rubric conflict recovery

## Trigger

The `hermes-upstream-rebase-ci` pre-run script woke at `stage: rebase` after rebasing the isolated worktree onto `upstream/main`. The only unmerged path was `AGENTS.md`.

The conflict was at the top of `AGENTS.md`:
- upstream had added a large `## What Hermes Is` / `## Contribution Rubric — What We Want / What We Don't` guidance block after `**Never give up on the right solution.**`;
- Brayan's personalization branch had added `## Brayan personalization branch rules` in the same area.

## Resolution pattern

Preserve both sides. Preferred final order:

1. Repo title and intro.
2. `**Never give up on the right solution.**`
3. `## Brayan personalization branch rules` block.
4. Upstream `## What Hermes Is` / contribution-rubric block.
5. Existing development-environment and project-structure sections.

This keeps Brayan's branch/push guardrails near the top while retaining upstream's new maintainer guidance.

## Low-risk edit path in autonomous cron

Cron runs may block arbitrary `python -c`, `execute_code`, or piping output into interpreters. If that happens, do not fight the approval layer. Use narrower git/file tools:

```bash
git checkout --ours AGENTS.md
```

Then apply a targeted patch that inserts the Brayan block immediately after `**Never give up on the right solution.**`. Verify with a conflict-marker search before continuing:

```bash
git add AGENTS.md
GIT_EDITOR=true git rebase --continue
```

After the rebase completes, if the live checkout must be advanced to the verified isolated-worktree candidate, create backup refs and use guarded ref movement rather than a broad destructive reset:

```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
candidate=$(git -C /home/brayan/.hermes/worktrees/hermes-upstream-rebase-ci rev-parse HEAD)
old=$(git rev-parse HEAD)
git update-ref refs/backup/hermes-upstream-ci/live-$ts $old
git update-ref refs/backup/hermes-upstream-ci/candidate-$ts $candidate
git update-ref refs/heads/brayan/personal-hermes-customizations $candidate $old
git read-tree --reset -u HEAD
```

Then use the skill-owned finalizer with `--apply`, inspect its `hermes_config_check` stdout for schema migrations, and if needed run `hermes config migrate` → sync personalization → commit allowed snapshot paths → rerun finalizer.

## Verification observed

The repaired run passed:
- finalizer/script `py_compile`;
- notes-intake and wake-gate focused tests;
- cron tooling tests;
- `hermes config check` after migration to the current config schema.
