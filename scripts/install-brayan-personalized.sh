#!/usr/bin/env bash
# Install Brayan's personalized Hermes Agent fork.
#
# Default target:
#   repo:   brayanb1701/hermes-agent
#   branch: second-computer-evolution
#   dir:    ~/.hermes/hermes-agent
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/second-computer-evolution/scripts/install-brayan-personalized.sh | bash
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
INSTALL_DIR="${HERMES_INSTALL_DIR:-${HOME}/.hermes/hermes-agent}"
HERMES_HOME_DIR="${HERMES_HOME:-${HOME}/.hermes}"

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
    --dir)
      if (( i + 1 >= ${#args[@]} )); then
        echo "error: --dir requires a value" >&2
        exit 2
      fi
      INSTALL_DIR="${args[$((i + 1))]}"
      ;;
    --hermes-home)
      if (( i + 1 >= ${#args[@]} )); then
        echo "error: --hermes-home requires a value" >&2
        exit 2
      fi
      HERMES_HOME_DIR="${args[$((i + 1))]}"
      ;;
    -h|--help)
      cat <<'HELP'
Install Brayan's personalized Hermes Agent fork.

Defaults:
  repo:   brayanb1701/hermes-agent
  branch: second-computer-evolution
  dir:    ~/.hermes/hermes-agent

Usage:
  curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/second-computer-evolution/scripts/install-brayan-personalized.sh | bash
  curl -fsSL https://raw.githubusercontent.com/brayanb1701/hermes-agent/second-computer-evolution/scripts/install-brayan-personalized.sh | bash -s -- --branch second-computer-evolution

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

existing_install=false
if [[ -d "$INSTALL_DIR/.git" ]]; then
  existing_install=true
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

install_dir="$INSTALL_DIR"
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

python_bin="$install_dir/venv/bin/python"
if [[ "$existing_install" == false && -x "$python_bin" && -f "$install_dir/scripts/apply-brayan-personalization.py" ]]; then
  "$python_bin" "$install_dir/scripts/apply-brayan-personalization.py" \
    --hermes-home "$HERMES_HOME_DIR" --apply --no-backup --preserve-config
  echo "Applied Brayan's agents, skills, plugins, scripts, cron jobs, and safe runtime files."
fi

if [[ -x "$python_bin" ]]; then
  "$python_bin" -m hermes_cli.main config set updates.branch "$INSTALL_SH_BRANCH" >/dev/null
  echo "Configured future Hermes updates to stay on ${INSTALL_SH_BRANCH}."
elif command -v hermes >/dev/null 2>&1; then
  hermes config set updates.branch "$INSTALL_SH_BRANCH" >/dev/null
  echo "Configured future Hermes updates to stay on ${INSTALL_SH_BRANCH}."
else
  echo "Hermes is not on PATH yet. After restarting the shell, run: hermes config set updates.branch '$INSTALL_SH_BRANCH'"
fi

cat <<'DONE'

Brayan personalized Hermes install finished.

Next recommended commands:
  source ~/.bashrc  # or source ~/.zshrc
  hermes config check
  hermes

Verify the selected maintenance branch:
  cd ~/.hermes/hermes-agent
  git status --short --branch
  git branch --show-current

Do not copy secrets from another machine into Git. Configure providers, Telegram, and local credentials through `hermes setup` or local config only.
DONE
