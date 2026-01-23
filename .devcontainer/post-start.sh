#!/usr/bin/env bash
set -euo pipefail
[[ ${DEBUG-} =~ ^1|yes|true$ ]] && set -o xtrace

# Color codes for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info() { printf "${GREEN}[INFO]${NC} %s\n" "$1"; }

# This script runs every time the container starts
# Add commands here that should run on container restart

log_info "Container started successfully!"
log_info "Use 'uv add <package>' to add Python dependencies"
log_info "Run 'azd up' to provision Azure resources"

printf "\n${GREEN}✅ DevContainer setup complete!${NC}\n\n"
printf "Next steps:\n"
printf "  - Start hacking your AI App right away! 🚀\n"
printf "  - Add python dependencies with 'uv add <package>'\n"
printf "  - Run 'azd up' to provision Azure resources\n"
