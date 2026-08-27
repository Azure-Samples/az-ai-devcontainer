# Infrastructure as Code documentation

## Current deployment flow

- The Foundry resource, project, and supporting resources are provisioned by Bicep during `azd up` or `azd provision`.
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

## Foundry Tools endpoints and RBAC

After provisioning, AZD writes Bicep outputs into the local environment file used by `azd env get-values`.

- `AZURE_AI_SERVICES_ENDPOINT` is the shared `AIServices` Foundry resource endpoint.
- `AZURE_AI_SERVICES_REGION` is the resource location for SDKs such as Speech and Translator that also require a region.
- `AZURE_CONTENT_UNDERSTANDING_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_CONTENT_SAFETY_ENDPOINT`, `AZURE_AI_VISION_ENDPOINT`, `AZURE_AI_LANGUAGE_ENDPOINT`, `AZURE_AI_SPEECH_ENDPOINT`, and `AZURE_AI_TRANSLATOR_ENDPOINT` are service-specific aliases for that same account.
- `AZURE_CONTENT_UNDERSTANDING_API_VERSION` is the current supported REST API version (`2025-11-01`) for analyzer operations.

The template disables local authentication and assigns the deployment principal
the **Cognitive Services User** role directly on the shared resource. This role
grants `Microsoft.CognitiveServices/*` data actions, which is the
least-privilege built-in role needed for passwordless tool API invocation. It
also assigns **Storage Blob Data Contributor** on the template storage account
for document input/output scenarios.

Verify local passwordless Document Intelligence and Content Understanding access after provisioning:

```bash
uv run python infra/scripts/verify_foundry_tools.py
```

The shared-resource approach avoids duplicate resources. Use a dedicated
single-service Document Intelligence resource only when you need isolation,
different regional placement, or separate billing; override its endpoint
without changing the template:

```bash
azd env set DOCUMENTINTELLIGENCE_ENDPOINT https://<your-document-intelligence-resource>.cognitiveservices.azure.com/
azd up
```

## Reusing existing resources

### Reusing an existing Microsoft Foundry resource

```bash
azd env new _new_environment_name_
azd env set USE_EXISTING_AI_FOUNDRY true
azd env set AI_FOUNDRY_NAME _existing_ai_foundry_name_
azd env set AI_FOUNDRY_ENDPOINT _existing_ai_foundry_endpoint_
azd env set AI_FOUNDRY_API_VERSION _existing_ai_foundry_api_version_
```

The template still creates a project under the existing Foundry resource. The
post-provision reconciler then ensures the selected model deployments exist on
that resource.

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
