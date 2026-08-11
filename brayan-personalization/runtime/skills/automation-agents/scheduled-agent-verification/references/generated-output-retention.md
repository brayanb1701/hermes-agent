# Generated-output retention verification

Use this when a scheduled agent writes dated files, rolling review entries, or appended recommendation sets.

## Durable pattern

1. Retain per generated series using a narrow filename or heading pattern. Never prune an entire shared directory, and never delete unrelated/manual files.
2. Run retention after the producer writes and verifies the new output. A pre-run cron script is only a cleanup guard; by itself it can leave `keep + 1` artifacts after today's write.
3. Treat rolling outputs as transient snapshots. Promote durable facts, decisions, blockers, outcomes, and evidence into canonical records before old snapshots age out.
4. Avoid durable wikilinks to transient outputs. Use plain code paths; rewrite links in retained rolling notes when their targets are pruned.
5. Make the helper idempotent and observable: provide `--dry-run`, emit before/kept/removed counts and paths, and verify a second dry-run requests no changes.
6. For histories inside one file, support the actual entry forms used by the agent (for example dated headings and dated bullets) while preserving non-generated prose.
7. Keep structural logs structural; routine cron runs should not duplicate their output into a central migration/system log.

## Test recipe

- Create a temporary fixture with more than the retention limit plus unrelated manual files/prose.
- Run retention and assert only the expected generated entries are removed.
- Assert manual files and non-generated prose remain.
- Assert retained notes have no wikilinks to deleted snapshots.
- Run a second dry-run and expect zero removals.
- Run the real producer once and verify the post-write count remains within the limit.

## Personalization bundle check

After changing live scripts, prompts, skills, or cron definitions, sync the personalization bundle. Inspect the generated diff before staging because the sync can surface unrelated live changes. Stage only the intended scope unless the user explicitly requests all pending changes. Verify script compilation, Hermes config, scoped/full `git diff --check`, and byte equality between live helpers and bundled copies.