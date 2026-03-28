# Infrastructure as Code documentation

## Current deployment flow

- The Foundry account, project, and supporting resources are provisioned by Bicep during `azd up` or `azd provision`.
- The model catalog is sourced from `infra/deployments.yaml` and reconciled after provisioning by `infra/scripts/deploy_models.py`.
- You can refresh API-backed fields in `infra/deployments.yaml` from the live account model catalog with `uv run python infra/scripts/sync_deployments_catalog.py --dry-run` and then rerun without `--dry-run` once the diff looks correct.
- Existing `sku.capacity` values are preserved by default so the sync does not overwrite your chosen deployment quota; pass `--sync-capacity` only if you want to reset them to Azure's current default capacity.
- Keep `--append-new` for manual curation only for now. The normal workflow is to review and add new models deliberately instead of bulk-appending everything Azure currently exposes.
- AZD runs `infra/hooks/postprovision.sh` automatically after provisioning unless `DEPLOY_AI_FOUNDRY_MODELS=false` is set in the AZD environment.
- You can run the same reconciler manually with `uv run python infra/scripts/deploy_models.py --mode manual`.

## Deploy with authentication enabled

> [!WARNING] 
> The account executing `azd` needs to be able to create Application Registrations in your Azure Entra ID tenant.

AZD can automatically configure authentication to secure the frontend and/or backend. To do so execute the following command before `azd up`:
```bash
azd env set USE_AUTHENTICATION true
```

If you already executed `azd up` just set the variable and run provisioning again:
```bash
azd env set USE_AUTHENTICATION true
azd provision
```

## Reusing existing resources

### Reusing an existing Azure AI Foundry resource

```bash
azd env new _new_environment_name_
azd env set USE_EXISTING_AI_FOUNDRY true
azd env set AI_FOUNDRY_NAME _existing_ai_foundry_name_
azd env set AI_FOUNDRY_ENDPOINT _existing_ai_foundry_endpoint_
azd env set AI_FOUNDRY_API_VERSION _existing_ai_foundry_api_version_
```

The template still creates a project under the existing Foundry resource. The post-provision reconciler then ensures the selected model deployments exist on that resource.

### Reusing an existing Azure AI Search Service

> [!CAUTION]
> Make sure you add the "Cognitive Services OpenAI User" role is assigned to the 
> User Assigned managed identity created for this deployment.


```bash
azd env new _your_environment_name_
azd env set USE_AI_SEARCH true
azd env set USE_EXISTING_AI_SEARCH true
azd env set AZURE_AI_SEARCH_NAME _existing_ai_search_name_

# If your Azure AI Search Service is in another resource group:
azd env set AZURE_AI_SEARCH_RESOURCE_GROUP_NAME _existing_ai_search_resource_group_name_
```
