#!/usr/bin/env bash
set -euo pipefail
[[ ${DEBUG-} =~ ^1|yes|true$ ]] && set -o xtrace

GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info() { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }

if ! command -v rg > /dev/null; then
    log_info "Installing ripgrep..."
    sudo apt-get update -qq
    sudo apt-get install --no-install-recommends -y -qq ripgrep
fi

# Install uv if not already installed
if ! command -v uv > /dev/null; then
    log_info "Installing UV package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Sync dependencies
log_info "Installing Python dependencies..."
uv sync --locked

printf "\n${GREEN}✅ DevContainer setup complete!${NC}\n\n"
printf "Next steps:\n"
printf "  - Start hacking your AI App right away! 🚀\n"
printf "  - Add python dependencies with 'uv add <package>'\n"
printf "  - Run 'azd up' to provision Azure resources\n"