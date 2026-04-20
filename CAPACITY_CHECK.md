# Azure AI Model Capacity Checker

This script checks if there is enough capacity available in your Azure region for all the models defined in [`infra/deployments.yaml`](infra/deployments.yaml).

## Prerequisites

1. **Azure CLI** installed and authenticated:
   ```bash
   az login
   ```

2. **Azure Developer CLI (azd)** installed and initialized:
   ```bash
   azd auth login
   azd init  # or azd env refresh if already initialized
   ```

3. **Python dependencies** installed:
   ```bash
   uv sync  # Dependencies are already added to pyproject.toml
   ```

## Usage

### Basic Usage

Check capacity in the region defined in your AZD environment:

```bash
python check_model_capacity.py
```

Or using the activated virtual environment:

```bash
.venv/bin/python check_model_capacity.py
```

### Specify a Different Region

Override the region from AZD environment:

```bash
python check_model_capacity.py --region eastus2
```

### Custom Deployments File

Use a different deployments configuration file:

```bash
python check_model_capacity.py --deployments custom/deployments.yaml
```

### Save Results to JSON

Export results to a JSON file for further analysis:

```bash
python check_model_capacity.py --output capacity_results.json
```

### Combined Options

```bash
python check_model_capacity.py \
  --region westeurope \
  --deployments infra/deployments.yaml \
  --output results.json
```

## Output

The script provides:

1. **Real-time progress** - Shows each model being checked with status indicators:
   - ✅ Available
   - ❌ Unavailable
   - ⚠️ Unknown (requires manual verification)
   - 🚨 Error

2. **Summary report** including:
   - Total models checked
   - Count of available, unavailable, and unknown models
   - List of models requiring manual verification
   - Any errors encountered

3. **Optional JSON export** with detailed results

## Example Output

```
🔐 Loading Azure Developer CLI environment...
📍 Subscription: 12345678-1234-1234-1234-123456789abc
📍 Region: eastus2
📂 Loading deployments from: infra/deployments.yaml

🔍 Checking capacity for 70 models in eastus2...
================================================================================
✅ OpenAI/gpt-4.1 v2025-04-14 - Available
✅ OpenAI/gpt-4.1-mini v2025-04-14 - Available
✅ OpenAI/gpt-4o v2024-11-20 - Available
...

================================================================================
📊 SUMMARY - Region: eastus2
================================================================================
Total models checked: 70
✅ Available: 68
❌ Unavailable: 0
⚠️  Unknown/Manual Check: 2
🚨 Errors: 0

💡 NOTE:
  GlobalStandard SKU models use pay-as-you-go pricing with no upfront
  capacity requirements. They are generally available across most regions.
  Some models may have regional restrictions (noted in deployments.yaml).
```

## Understanding the Results

### GlobalStandard SKU

Most models in the deployments.yaml use **GlobalStandard** SKU, which means:
- ✅ Pay-as-you-go pricing
- ✅ No running costs when not in use
- ✅ Generally available across most Azure regions
- ⚠️ Some models have regional restrictions (e.g., o3-pro, codex-mini only in East US2 & Sweden Central)

### Regional Restrictions

Some models are only available in specific regions:
- **o3-pro**: East US2, Sweden Central only
- **codex-mini**: East US2, Sweden Central only  
- **gpt-5.2-codex**: East US2, Sweden Central only
- **Image/Video models** (commented out): Limited regions

Check the comments in `infra/deployments.yaml` for specific regional availability.

## Troubleshooting

### "AZURE_SUBSCRIPTION_ID not found"

Run `azd env refresh` to reload environment variables:
```bash
azd env refresh
```

### "Failed to load AZD environment"

Make sure you've initialized an AZD environment:
```bash
azd init
azd auth login
```

### "Azure Developer CLI (azd) not found"

Install azd:
- **Linux/macOS**: `curl -fsSL https://aka.ms/install-azd.sh | bash`
- **Windows**: `winget install microsoft.azd`
- See: https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/

### Authentication Issues

Ensure you're logged into Azure CLI:
```bash
az login
az account show  # Verify correct subscription
```

## Technical Details

The script:
1. Loads environment variables from AZD using `azd env get-values`
2. Parses the `infra/deployments.yaml` file
3. Uses `DefaultAzureCredential` for Azure authentication
4. Checks capacity using Azure Cognitive Services Management SDK
5. Reports availability for each model

## Limitations

- **GlobalStandard models**: The script marks them as "available" since they use pay-as-you-go with no upfront capacity. Actual deployment may still fail due to regional restrictions.
- **Real-time capacity**: Azure doesn't provide a direct API to check real-time capacity for all model types. This script provides a best-effort check.
- **Manual verification**: Some models may require manual testing by attempting a deployment.

## See Also

- [Azure AI Foundry Models Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure)
- [Azure Model Catalog](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/model-catalog)
- [Model Regional Availability](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#model-summary-table-and-region-availability)
