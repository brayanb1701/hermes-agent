# Autoresearch Commander

Reusable file-defined pattern for autonomous research/code challenge loops.

Use this directory only for the generalized pattern. Put challenge-specific missions, prompts, launchers, logs, feedback files, and experiment artifacts under `/home/brayan/projects/<experiment>/`.

Core idea: adapt Karpathy's `autoresearch` loop to Darwin/Hermes/Codex: continuously inspect constraints, propose experiments, edit code, run bounded tests, parse metrics, keep/revert, log, check human feedback, and continue until a stop file or explicit human stop.
