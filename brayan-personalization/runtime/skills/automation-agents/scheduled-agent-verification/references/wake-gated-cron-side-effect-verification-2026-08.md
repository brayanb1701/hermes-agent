# 2026-08 wake-gated cron push verification

Use this as a concrete verification example for wake-gated cron jobs whose local cron output only says the script skipped the LLM agent.

## Lesson

Cron `Result: ok` or `Script gate returned wakeAgent=false` proves only that the scheduler accepted the pre-run script result and skipped the agent. It does not prove the script's external side effects happened.

For side-effecting wake gates, verify the script's own durable evidence and the external state it claims to changed.

## Evidence stack

1. Read the cron output to identify job ID and run time.
2. Locate the script-specific log written by the pre-run script.
3. Verify the script log has a successful domain status, not just `wakeAgent=false`.
4. Verify side-effect evidence independently:
   - For Git push jobs: push command return code plus remote SHA after fetch/`ls-remote`.
   - For activation/deploy jobs: activation scheduling evidence plus a follow-up run or status probe proving live state matches candidate.
5. If a first run schedules detached activation, run or wait for one follow-up check; success is the follow-up `up_to_date`/no-op state, not merely the first run's scheduled timer.

## Concrete observed pattern

For `hermes-upstream-rebase-ci`:

- A manual run returned cron `ok` with `wakeAgent=false`, while the updater JSON showed `status: personalization_synced`, a real Git push, and detached live activation scheduled.
- A later run showed `status: up_to_date`, `activation_scheduled: false`, and matching live/origin/candidate SHA. That second no-op run is the proof that push + activation completed.

## Pitfall

Do not declare the next scheduled run healthy when the live checkout is dirty. Some cron scripts intentionally refuse dirty live state at preflight, even if the dirty files are intended follow-up cleanup.
