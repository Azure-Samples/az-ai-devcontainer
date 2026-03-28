#!/usr/bin/env bash
set -euo pipefail

if [[ "${DEPLOY_AI_FOUNDRY_MODELS:-true}" != "true" ]]; then
  echo "Skipping model deployment reconciliation because DEPLOY_AI_FOUNDRY_MODELS is not true."
  exit 0
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

if command -v uv >/dev/null 2>&1; then
  uv run python infra/scripts/deploy_models.py --mode hook
else
  python3 infra/scripts/deploy_models.py --mode hook
fi