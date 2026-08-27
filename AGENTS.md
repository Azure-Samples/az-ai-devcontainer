# AI Agent Instructions

## Project

This repository is a Python 3.13 development-container template for Microsoft
Foundry. It provisions Azure infrastructure with Bicep and Azure Developer CLI
(`azd`) and includes a Jupyter notebook for experimentation.

Key locations:

- `.devcontainer/`: container configuration and lifecycle scripts
- `infra/main.bicep`: Azure infrastructure
- `infra/deployments.yaml`: curated Foundry model deployments
- `infra/scripts/`: model maintenance and access-verification CLIs
- `notebooks/`: clean, documented Jupyter samples
- `tests/`: pytest tests for repository tooling

## Tooling

- Use `uv` for Python dependency management; never edit dependency declarations
  or `uv.lock` manually.
- Run Python with `uv run python <script>`.
- Add runtime dependencies with `uv add <package>`.
- Add development dependencies with `uv add --dev <package>`.
- Use Ruff with an 88-character line length and pytest for tests.

Common checks:

```bash
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest
az bicep build --file infra/main.bicep
```

## Conventions

### Python

- Follow PEP 8 and use type hints for function signatures.
- Use Google-style docstrings for public functions.
- Group standard-library, third-party, and local imports.
- Keep CLI behavior explicit: surface errors and avoid broad silent fallbacks.

### Bicep

- Prefer Azure Verified Modules.
- Use resource abbreviations from `infra/abbreviations.json`.
- Add `@description` to parameters and outputs.
- Apply the `azd-env-name` and `solution` tags to provisioned resources.
- Export values required by samples or downstream applications.

### Shell

- Start scripts with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Keep scripts idempotent and use the existing logging style.

### Notebooks

- Load the active environment with `azd env get-values` in the first code cell.
- Authenticate with `DefaultAzureCredential`.
- Include Markdown explanations and clear all outputs before committing.

## Safety and scope

- Never hardcode credentials; use environment variables and Azure Identity.
- Preserve the repository structure unless a task explicitly changes it.
- Follow existing patterns before adding new abstractions.
- Update directly related documentation and tests with behavior changes.
- Validate locally before committing.

## References

- [Microsoft Foundry SDKs and endpoints](https://learn.microsoft.com/azure/foundry/how-to/develop/sdk-overview)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/)
- [Development Containers](https://containers.dev/)
- [uv](https://docs.astral.sh/uv/)
