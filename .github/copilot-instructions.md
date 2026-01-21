# GitHub Copilot Instructions

This file provides instructions for GitHub Copilot when working in this repository.

## Primary Reference

**Always read and follow the guidelines in [AGENTS.md](../AGENTS.md)** - it contains comprehensive instructions for AI agents working with this codebase.

## Quick Reference

### Project Type
Azure AI DevContainer template with Python, Bicep infrastructure, and Jupyter notebooks.

### Key Technologies
- **Python 3.13** with UV package manager
- **Bicep** for Azure infrastructure
- **Azure AI Foundry** SDK for AI development
- **DevContainers** for development environment

### Code Style
- Python: PEP 8, Ruff formatter/linter (line length 88), Google-style docstrings
- Bicep: Azure Verified Modules (AVM), descriptive parameters
- Shell: Bash with strict mode (`set -euo pipefail`)

### Critical Rules
1. Never hardcode credentials - use environment variables
2. Use `uv add` for dependencies, not manual pyproject.toml edits
3. For Bicep, prefer AVM modules from `br/public:avm/`
4. Always use `DefaultAzureCredential()` for Azure authentication
5. Load environment from AZD in notebooks before Azure calls

### File Patterns
- Infrastructure changes → `infra/*.bicep`
- Python dependencies → `pyproject.toml` via `uv add`
- Notebooks → `notebooks/` directory
- DevContainer config → `.devcontainer/`

## See Also
- [AGENTS.md](../AGENTS.md) - Full agent instructions
- [README.md](../README.md) - Project documentation
- [infra/README.md](../infra/README.md) - Infrastructure documentation
