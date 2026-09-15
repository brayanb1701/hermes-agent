# Busy input and steering

Treat steering as a correction consumed at the next safe action/model boundary, without aborting active tools. Herdr prompt delivers paste + Enter; --wait is lifecycle observation, not a message receipt. Never send Esc/Ctrl+C as an automatic steering prelude. Inspect approval dialogs before input; agent detection can incorrectly report idle/done while a dialog is visible.

## Native routes
- Hermes CLI: display.busy_input_mode = steer. Native /busy steer updates an existing session; a config-file change alone does not prove existing sessions changed. Images or rejected steering can fall back to next-turn queue. Test target: tests/cli/test_cli_steer_busy_path.py and test_busy_input_mode_command.py through scripts/run_tests.sh.
- Codex 0.153.4: default submit Enter, queue Tab. Version-matched tui/keymap.rs and chatwidget/input_submission.rs track busy submissions as pending_steers; no keymap override was present on Calcifer or DarkArmy. Do not add a removed steer feature flag.
- Pi: interactive-mode submits streaming text with streamingBehavior: steer; followUp is a separate path. steeringMode all/one-at-a-time controls batching, not steering versus follow-up. Check keybinding overrides, not just settings.
- OMP 17.4.0: Enter selects steer, but default interruptMode immediate can abort/background active tools. Set native interruptMode wait for boundary-safe steering; verify with omp config get interruptMode --json. Do not confuse this with followUpMode or steeringMode.
- Claude Code 2.1.270: live Herdr test submitted correction during an active 25-second Python tool; native transcript showed successful completion of that tool, then the corrected command, not the original planned command. Enter already has the desired behavior; no extra setting required. Official docs: https://code.claude.com/docs/en/how-claude-code-works#interrupt-and-steer
- Antigravity: live test on 1.2.2 with Gemini 3.8 Flash accepted busy Enter correction and selected the corrected next command. It auto-backgrounded the long tool, so this does not prove the same foreground-turn timing as Claude. No documented steer-mode setting found; never invent one. Preserve user approvals. Official settings: https://antigravity.google/docs/cli/settings

## Operational limits

Native defaults and source tests are not live end-to-end verification on every host/model. Require explicit acknowledgment for important corrections. Cross-session deadlocks still need a non-blocking question/reply protocol.

Inspect launcher scripts before version checks: DarkArmy's Pi/OMP wrappers run mise use and can install or upgrade. An OMP launcher is not proof of an installed OMP runtime. Antigravity may self-update between launches; record the actual running version, not just the earlier --version output. Avoid bulk restarts of unrelated sessions to apply input defaults.
