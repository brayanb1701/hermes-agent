# OpenCode v2 compatibility

Check https://herdr.dev/llms.txt and official upstream integration assets before authoring a custom fix. Herdr 0.8.2 bundles OpenCode integration v10 (V1-only); stable v0.9.0 assets v11 also lack the v2 default export. Upstream commit aa961df943b874730b23f78baf94af7332f7acfa has v12 V1/V2 assets. On Calcifer those official server/TUI assets were installed with old copies under ~/.config/opencode/herdr-v10-backup. The Herdr binary/server was not updated.

OpenCode v2 uses a shared server: pane-specific lifecycle and selected root identity must report from its CLI plugin, not the server's inherited environment. V12 server setup is intentionally a no-op for v2.

For OpenCode 2.0.3, registering the bare herdr-tui-session.js file in cli.json did not load the CLI plugin. A local package at ~/.config/opencode/herdr-v2-cli with package.json exports {"./tui":"./tui.js"} and tui.js re-exporting ../herdr-tui-session.js worked; cli.json plugins lists that package's absolute path. Preserve this registration until the upstream installer supports the tested layout.

Verify real agent_session source herdr:opencode and screen_detection_skipped:true in herdr agent get, plus prompt lifecycle and actual output. An integration status 'current' only means the file matches the installed Herdr bundle, not runtime compatibility. Do not reinstall via the older Herdr binary: it overwrites v12 assets with incompatible v10. Upgrade to a release carrying v2 support before returning to managed installs.
