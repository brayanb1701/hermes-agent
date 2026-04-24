#!/usr/bin/env bash
# Install Brayan's personalized Hermes Agent fork.
#
# Default target:
#   repo:   brayanb1701/hermes-agent
#   branch: second-computer-evolution
#   dir:    ~/.hermes/hermes-agent
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/main/scripts/install-brayan-personalized.sh | bash
#
# Options are forwarded to scripts/install.sh. Common examples:
#   bash install-brayan-personalized.sh --branch main
#   bash install-brayan-personalized.sh --branch second-computer-evolution --skip-setup
#   bash install-brayan-personalized.sh --dir ~/.hermes/hermes-agent-lab

set -euo pipefail

FORK_OWNER="${HERMES_PERSONAL_FORK_OWNER:-brayanb1701}"
FORK_REPO="${HERMES_PERSONAL_FORK_REPO:-hermes-agent}"
DEFAULT_BRANCH="${HERMES_PERSONAL_BRANCH:-second-computer-evolution}"
INSTALL_SH_BRANCH="$DEFAULT_BRANCH"

args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[$i]}" in
    --branch)
      if (( i + 1 >= ${#args[@]} )); then
        echo "error: --branch requires a value" >&2
        exit 2
      fi
      INSTALL_SH_BRANCH="${args[$((i + 1))]}"
      ;;
    -h|--help)
      cat <<'HELP'
Install Brayan's personalized Hermes Agent fork.

Defaults:
  repo:   brayanb1701/hermes-agent
  branch: second-computer-evolution
  dir:    ~/.hermes/hermes-agent

Usage:
  curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/main/scripts/install-brayan-personalized.sh | bash
  curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/main/scripts/install-brayan-personalized.sh | bash -s -- --branch main

Forwarded options from scripts/install.sh:
  --branch NAME        Branch to install
  --dir PATH           Installation directory
  --hermes-home PATH   Hermes data directory
  --skip-setup         Skip interactive setup wizard
  --no-venv            Do not create venv
HELP
      exit 0
      ;;
  esac
done

if [[ " ${args[*]} " != *" --branch "* ]]; then
  args+=(--branch "$DEFAULT_BRANCH")
fi

export HERMES_REPO_URL_SSH="git@github.com:${FORK_OWNER}/${FORK_REPO}.git"
export HERMES_REPO_URL_HTTPS="https://github.com/${FORK_OWNER}/${FORK_REPO}.git"

raw_base="https://raw.githubusercontent.com/${FORK_OWNER}/${FORK_REPO}/${INSTALL_SH_BRANCH}"
installer_url="${raw_base}/scripts/install.sh"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
installer="$tmp_dir/install.sh"

echo "Installing Brayan Hermes from ${HERMES_REPO_URL_HTTPS} (${INSTALL_SH_BRANCH})"

if [[ -f "scripts/install.sh" && -d ".git" ]]; then
  # Running from a checked-out repository; use the local installer so edits can be tested before push.
  bash scripts/install.sh "${args[@]}"
else
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$installer_url" -o "$installer"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$installer" "$installer_url"
  else
    echo "error: need curl or wget to download $installer_url" >&2
    exit 1
  fi
  bash "$installer" "${args[@]}"
fi

install_dir="${HERMES_INSTALL_DIR:-${HOME}/.hermes/hermes-agent}"
if [[ -d "$install_dir/.git" ]]; then
  cd "$install_dir"
  git remote set-url origin "$HERMES_REPO_URL_SSH" 2>/dev/null || git remote add origin "$HERMES_REPO_URL_SSH"
  if git remote get-url upstream >/dev/null 2>&1; then
    git remote set-url upstream git@github.com:NousResearch/hermes-agent.git
  else
    git remote add upstream git@github.com:NousResearch/hermes-agent.git
  fi
  git fetch origin --quiet || true
  git fetch upstream --quiet || true
fi

if command -v hermes >/dev/null 2>&1; then
  hermes config set model.provider openai-codex >/dev/null 2>&1 || true
  hermes config set model.default gpt-5.5 >/dev/null 2>&1 || true
  echo "Configured Hermes default text model to openai-codex:gpt-5.5 when supported."
else
  echo "Hermes command is not on PATH yet. Restart the shell, then run: hermes config set model.default gpt-5.5"
fi

cat <<'DONE'

Brayan personalized Hermes install finished.

Next recommended commands:
  source ~/.bashrc  # or source ~/.zshrc
  hermes config check
  hermes

If this machine is the independent evolution line:
  cd ~/.hermes/hermes-agent
  git status --short --branch
  git branch --show-current   # should be second-computer-evolution unless you chose another branch

Do not copy secrets from another machine into Git. Configure providers, Telegram, and local credentials through `hermes setup` or local config only.
DONE
