# AI Agent Instructions

This file provides guidance for AI agents (GitHub Copilot, Claude, etc.) working with this repository.

## Project Overview

This is an **Azure AI DevContainer template** for Python-based AI development projects. It provides:
- A pre-configured Development Container for VS Code and GitHub Codespaces
- Azure infrastructure and Microsoft Foundry provisioning via Bicep and Azure Developer CLI (AZD)
- Jupyter Notebook support for AI experimentation
- Integration with Microsoft Foundry services

## Repository Structure

```
.
├── .devcontainer/          # DevContainer configuration
│   ├── devcontainer.json   # Main configuration
│   └── post-create.sh      # Setup script run after container creation
├── .github/                # GitHub configuration
│   └── copilot-instructions.md  # Copilot-specific guidelines
├── .vscode/                # VS Code settings
│   └── extensions.json     # Recommended extensions
├── infra/                  # Azure infrastructure (Bicep)
│   ├── main.bicep          # Main infrastructure definition
│   ├── main.parameters.json # Parameters
│   ├── deployments.yaml    # AI model deployment configs
│   ├── hooks/              # AZD lifecycle hooks
│   ├── scripts/            # Model catalog and deployment utilities
│   └── abbreviations.json  # Resource naming abbreviations
├── notebooks/              # Jupyter notebooks
│   └── SampleNotebook.ipynb
├── azure.yaml              # Azure Developer CLI configuration
├── pyproject.toml          # Python project configuration (UV)
└── README.md               # Project documentation
```

## Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.13 |
| Package Manager | [UV](https://docs.astral.sh/uv/) (preferred) |
| Infrastructure | [Bicep](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/) |
| CLI Tools | Azure CLI (`az`), Azure Developer CLI (`azd`), GitHub CLI (`gh`) |
| Cloud | Azure (AI Foundry, Storage, Search, App Insights) |
| Container | DevContainers / GitHub Codespaces |

Always use `uv` for dependency management but also to run commands in the proper
environment. The DevContainer automatically sets up a Python virtual environment 
and installs dependencies from `pyproject.toml` when the container is created.
Run python commands with `uv run python <script>` to ensure they execute in 
the correct environment. For Python tools use `uvx <tool>` (e.g. `uvx black .` to 
format code with Black).

## Coding Guidelines

### Python

1. **Style**: Follow PEP 8, use Ruff for formatting and linting (line length 88)
2. **Imports**: Group standard library, third-party, and local imports (Ruff handles this automatically)
3. **Type Hints**: Use type hints for function signatures
4. **Docstrings**: Use Google-style docstrings
5. **Dependencies**: Add via `uv add <package>`, never edit pyproject.toml directly

```python
# Example function format
def process_data(input_data: dict[str, Any], *, verbose: bool = False) -> list[str]:
    """Process input data and return results.
    
    Args:
        input_data: Dictionary containing the data to process.
        verbose: If True, print detailed progress.
    
    Returns:
        List of processed string results.
    
    Raises:
        ValueError: If input_data is empty.
    """
    ...
```

### Bicep / Infrastructure

1. **Naming**: Use abbreviations from `infra/abbreviations.json`
2. **Modules**: Prefer Azure Verified Modules (AVM) from `br/public:avm/`
3. **Parameters**: Document all parameters with `@description`
4. **Outputs**: Export all values needed by applications
5. **Tags**: Always include `azd-env-name` and `solution` tags

### Shell Scripts

1. **Shebang**: Always start with `#!/usr/bin/env bash`
2. **Strict Mode**: Always set `set -euo pipefail`
3. **Idempotency**: Scripts should be safe to run multiple times
4. **Logging**: Use color-coded log functions for visibility

### Jupyter Notebooks

1. **First Cell**: Always load environment from AZD (`azd env get-values`)
2. **Credentials**: Use `DefaultAzureCredential()` for Azure authentication
3. **Outputs**: Clear outputs before committing (keep notebooks clean)
4. **Documentation**: Include markdown cells explaining each section

## Environment Variables

Key environment variables (set by AZD after `azd up`):

| Variable | Description |
|----------|-------------|
| `AI_FOUNDRY_PROJECT_ENDPOINT` | Primary Azure AI Foundry project endpoint used by the sample notebook |
| `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT` | AI Foundry project endpoint |
| `AI_FOUNDRY_PROJECT_NAME` | Azure AI Foundry project name |
| `AI_FOUNDRY_NAME` | Azure AI Foundry account name |
| `AI_FOUNDRY_ENDPOINT` | Azure AI Foundry account endpoint |
| `AI_FOUNDRY_DEPLOYMENT_NAME` | Default model deployment name |
| `AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME` | Fallback deployment name used by agent-oriented samples |
| `AZURE_OPENAI_API_VERSION` | API version for OpenAI calls |
| `AZURE_RESOURCE_GROUP` | Resource group that contains the deployed resources |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription that contains the deployed resources |
| `AZURE_AI_SEARCH_ENDPOINT` | Azure AI Search endpoint (if enabled) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights connection |

Load these in Python:
```python
from dotenv import load_dotenv
load_dotenv()  # or use AZD env loading pattern from SampleNotebook.ipynb
```

## Common Tasks

### Adding Python Dependencies
```bash
uv add <package-name>
# For dev dependencies:
uv add --dev <package-name>
```

### Running Azure Provisioning
```bash
azd auth login  # First time only
azd up          # Provision and deploy
azd down        # Tear down resources
```

### Working with Notebooks
1. Open notebook in VS Code
2. Select Python kernel from `.venv`
3. Run first cell to load environment
4. Develop interactively

## Important Notes for Agents

1. **Never hardcode credentials** - Always use environment variables or Azure Identity
2. **Check existing patterns** - Look at existing code before generating new code
3. **Preserve structure** - Don't reorganize files without explicit request
4. **Test locally first** - Ensure code works in the DevContainer
5. **Document changes** - Update relevant documentation when making changes
6. **Use AVM modules** - For Bicep, prefer Azure Verified Modules over raw resources

## Related Documentation

- [Azure AI Foundry SDK](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/develop/sdk-overview)
- [Azure Developer CLI](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/)
- [DevContainers Specification](https://containers.dev/)
- [UV Package Manager](https://docs.astral.sh/uv/)
