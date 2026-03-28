# Infrastructure as Code documentation

## Current deployment flow

- The Foundry account, project, and supporting resources are provisioned by Bicep during `azd up` or `azd provision`.
- The model catalog is still sourced from `infra/deployments.yaml` during provisioning today.
- A separate post-provision model deployment stage is planned, but it is intentionally not enabled yet.

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

The template still creates a project under the existing Foundry resource. Model rollout automation is a separate stage and is not enabled yet.

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
