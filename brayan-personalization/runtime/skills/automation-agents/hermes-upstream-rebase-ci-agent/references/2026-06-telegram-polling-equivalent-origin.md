# 2026-06 Telegram polling fix false divergence

## Symptom

The daily Hermes upstream rebase CI woke at `stage: preflight` because live `brayan/personal-hermes-customizations` and `origin/brayan/personal-hermes-customizations` diverged. `git cherry -v origin/brayan/personal-hermes-customizations HEAD` showed one live-only `+` commit:

- `fix: preserve Telegram updates during polling startup`

Most other live-only commits were patch-equivalent (`-`).

## Root cause

The apparent live-only fix was already preserved on origin, but upstream had refactored the Telegram adapter path from:

- `gateway/platforms/telegram.py`

to:

- `plugins/platforms/telegram/adapter.py`

Because the same behavior lived at a different file path / hunk context, `git cherry` could not classify the old live commit as patch-equivalent.

## Evidence pattern

Before choosing a base, compare by behavior, not just patch ID:

```bash
git log --all --format='%H %D %ci %s' --grep='preserve Telegram updates' --regexp-ignore-case
git range-diff <live-fix>^..<live-fix> <origin-fix>^..<origin-fix>
git grep -n 'drop_pending_updates=False' origin/brayan/personal-hermes-customizations -- \
  gateway/platforms/telegram.py plugins/platforms/telegram/adapter.py
git grep -n 'test_polling_connect_preserves_pending_updates' origin/brayan/personal-hermes-customizations -- \
  tests/gateway/test_telegram_conflict.py tests/gateway/test_telegram_platform.py
```

Origin was safe to use as the base only because it contained all of:

1. a same-subject `fix: preserve Telegram updates during polling startup` commit;
2. `drop_pending_updates=False` in the current Telegram adapter path;
3. regression test `test_polling_connect_preserves_pending_updates`.

## Durable fix applied

The wake-gate script was patched to treat this one known `+` commit as equivalent only when the above guards pass. It uses `git grep` over both old and new adapter/test paths instead of `git show <ref>:<path>`, because `git show` fails when any candidate path is absent on that ref.

## Recovery sequence

1. Create backup refs for live and old origin heads.
2. Choose origin as the safe base after the guarded behavioral check.
3. Rerun the pre-run script deliberately.
4. Let it sync personalization, rebase onto `upstream/main`, run tests/config check, and push with exact force-with-lease.
5. Move the live checkout to the verified origin head with guarded `git update-ref` + `git read-tree --reset -u HEAD` when the live worktree is clean.
6. Run the skill-owned finalizer as a post-check; `stage: no_op` is expected if origin already matches live.

## Verification observed

- `py_compile` passed.
- Focused intake/wake-gate tests passed.
- Cron/tooling tests passed.
- `hermes config check` reported current config version.
- `origin...HEAD` became `0 0`.
- `upstream/main` was an ancestor of `HEAD`.
