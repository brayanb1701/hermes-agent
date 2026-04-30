#!/usr/bin/env bash
set -euo pipefail
SESSION="parameter-golf-commander"
PROMPT="/home/brayan/.hermes/agents/parameter-golf-commander/initial-prompt.md"
cd /home/brayan/projects/parameter-golf
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session already exists: $SESSION"
  exit 0
fi
tmux new-session -d -s "$SESSION" -x 160 -y 48 'hermes chat --provider openai-codex --model gpt-5.5 --skills hermes-agent,personal-vault-ops,file-defined-hermes-agents,subagent-driven-development --toolsets terminal,file,web,delegation,skills,todo,session_search --max-turns 120 --yolo --pass-session-id'
sleep 8
# Best-effort set maximum reasoning in interactive Hermes. If unsupported, it will be harmless text/command feedback in the session.
tmux send-keys -t "$SESSION" '/reasoning xhigh' Enter
sleep 2
tmux load-buffer -b parameter_golf_prompt "$PROMPT"
tmux paste-buffer -t "$SESSION" -b parameter_golf_prompt
tmux send-keys -t "$SESSION" Enter
echo "launched tmux session: $SESSION"
echo "attach: tmux attach -t $SESSION"
echo "capture: tmux capture-pane -t $SESSION -p | tail -120"
