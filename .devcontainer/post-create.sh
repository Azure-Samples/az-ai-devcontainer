#!/usr/bin/env bash
set -euo pipefail
[[ ${DEBUG-} =~ ^1|yes|true$ ]] && set -o xtrace

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }
log_warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
log_error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

# Update packages (with caching check)
log_info "Updating package list..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    log_info "Installing UV package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
else
    log_info "UV already installed, skipping..."
fi

# Sync dependencies
log_info "Installing Python dependencies..."
uv sync

# Install mise (polyglot runtime manager) if not already installed
log_info "Installing mise (runtime version manager)..."
curl https://mise.run/bash | sh

log_info "Installing uv..."
mise use -g uv

log_info "Installing ruff..."
mise use -g ruff 

log_info "Installing Starship prompt..."
mise use -g starship 

mise install starship 
log_info "Adding Starship to .bashrc..."
echo 'eval "$(starship init bash)"' >> ~/.bashrc

printf "\n${GREEN}✅ DevContainer setup complete!${NC}\n\n"
printf "Next steps:\n"
printf "  - Start hacking your AI App right away! 🚀\n"
printf "  - Add python dependencies with 'uv add <package>'\n"
printf "  - See https://docs.astral.sh/uv/ for more information\n\n"


