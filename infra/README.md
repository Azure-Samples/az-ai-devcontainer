# Infrastructure as Code documentation

## Current deployment flow

- The Foundry account, project, and supporting resources are provisioned by Bicep during `azd up` or `azd provision`.
- The intentionally small model catalog is sourced from `infra/deployments.yaml`.
- Use `uv run python infra/scripts/models.py preview` to preview both live catalog metadata changes and deployment reconciliation.
- Use `uv run python infra/scripts/models.py upgrade --apply` to refresh the curated entries and deploy them.
- Use `uv run python infra/scripts/models.py deploy --dry-run` when only the deployment diff is needed.
- Add `--prune` to a deployment dry run to list live deployments absent from the curated catalog. Run without `--dry-run` only after reviewing the destructive deletion list.
- Existing `sku.capacity` values are preserved by default so the sync does not overwrite your chosen deployment quota; pass `--sync-capacity` only if you want to reset them to Azure's current default capacity.
- New models are added to `infra/deployments.yaml` deliberately after checking live model availability and quota. The normal workflow never bulk-appends the Azure catalog.
- AZD runs `infra/hooks/postprovision.sh` automatically after provisioning unless `DEPLOY_AI_FOUNDRY_MODELS=false` is set in the AZD environment.
- Expected Azure-side blockers such as deprecating models, gated access, marketplace policy, and insufficient quota are reported without failing the entire AZD provision. Unexpected errors still fail.

## Authentication status

This template does not currently provision application registrations, secrets, or frontend/backend authentication resources.

If you need authenticated application components, add them explicitly in your own infrastructure and application code rather than relying on a built-in `USE_AUTHENTICATION` workflow.

## Service endpoints exposed through AZD

After provisioning, AZD writes Bicep outputs into the local environment file used by `azd env get-values`.

- `CONTENTUNDERSTANDING_ENDPOINT` and `AZURE_CONTENT_UNDERSTANDING_ENDPOINT` always reuse the Foundry account endpoint because Azure Content Understanding uses the Microsoft Foundry resource endpoint.
- `DOCUMENTINTELLIGENCE_ENDPOINT` and `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` default to the same Foundry endpoint so you can start with a shared endpoint and no extra deployment.

If you want to override the Document Intelligence endpoint without changing the template, set it in the AZD environment before running `azd up`:

```bash
azd env set DOCUMENTINTELLIGENCE_ENDPOINT https://<your-document-intelligence-resource>.cognitiveservices.azure.com/
azd up
```

This is the recommended path when you need a dedicated single-service Document Intelligence resource, such as Microsoft Entra ID authentication with the Document Intelligence SDK.

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
> This template does not create RBAC assignments for an existing Azure AI Search service.
> Grant any required roles separately to the identities or users that will access that service.


```bash
azd env new _your_environment_name_
azd env set USE_AI_SEARCH true
azd env set USE_EXISTING_AI_SEARCH true
azd env set AZURE_AI_SEARCH_NAME _existing_ai_search_name_

# If your Azure AI Search Service is in another resource group:
azd env set AZURE_AI_SEARCH_RESOURCE_GROUP_NAME _existing_ai_search_resource_group_name_

# Optional: set the location if you want it propagated in the AZD environment:
azd env set AZURE_AI_SEARCH_LOCATION _existing_ai_search_location_
```
