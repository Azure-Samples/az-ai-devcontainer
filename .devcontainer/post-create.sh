#!/usr/bin/env bash
set -euo pipefail
[[ ${DEBUG-} =~ ^1|yes|true$ ]] && set -o xtrace

# Update the package list and upgrade all packages
sudo apt update
sudo apt upgrade -y

# Install uv, see https://astral.sh for additional information
curl -LsSf https://astral.sh/uv/install.sh | sh
echo 'export UV_LINK_MODE=copy' >> $HOME/.bashrc
source $HOME/.bashrc

uv sync

# Install Staship prompt
curl -sS https://starship.rs/install.sh | sh -s -- -y
echo 'eval "$(starship init bash)"' >> ~/.bashrc
source ~/.bashrc

printf "\n\n\033[1m✅ DevContainer was successfully created!\033[0m\n\n"
printf "Next steps: \n"
printf "  - Start hacking your AI App right away! 🚀\n"
printf "  - Add python dependencies to pyproject.yaml by running 'uv add <package>'\n"
printf "  - See https://docs.astral.sh/uv/ for more information\n"


