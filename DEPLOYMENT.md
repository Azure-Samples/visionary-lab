# Azure Deployment with Azure Developer CLI (azd)

This guide shows how to deploy the Visionary Lab to Azure using the Azure Developer CLI for one-click deployments.

## Prerequisites

- [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) installed
- Azure subscription with access to:
  - Azure AI Foundry (AIServices)
  - Azure Container Apps
  - Azure Storage Account
  - Azure Cosmos DB
  - Azure Log Analytics

## Quick Start (One-Click Deployment)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd visionary-lab
   ```

2. **Authenticate and deploy**:
   ```bash
   azd auth login
   azd up
   ```

3. **Configure during deployment**:
   When prompted by `azd up`, provide:

   - **AI_FOUNDRY_NAME**: Name for your AI Foundry resource (must be globally unique)
   - **AI_FOUNDRY_LOCATION**: Azure region for AI Foundry (default: `swedencentral`)
   - **LLM_DEPLOYMENT**: LLM deployment name (default: `gpt-4o`)
   - **IMAGEGEN_DEPLOYMENT**: Image generation deployment name (default: `gpt-image-1-5`)
   - **SORA_DEPLOYMENT**: Video generation deployment name (default: `sora`)

   > **No API keys required.** All services use Azure Managed Identity for authentication.

That's it! The `azd up` command will:
- Create a new environment
- Provision the AI Foundry resource with all model deployments
- Provision Storage, Cosmos DB, Container Registry, Container Apps
- Assign RBAC roles (Cognitive Services OpenAI User, Storage Blob Data Contributor, etc.)
- Build and deploy Docker images for frontend and backend
- Configure networking and environment variables
- Provide you with the application URLs

## Manual Steps

If you prefer manual control over the deployment process:

### 1. Initialize Environment
```bash
azd env new <environment-name>
```

### 2. Configure Environment Variables
```bash
# AI Foundry
azd env set AI_FOUNDRY_NAME "your-foundry-name"
azd env set AI_FOUNDRY_LOCATION "swedencentral"

# Model deployments (names must match what gets deployed)
azd env set LLM_DEPLOYMENT "gpt-4o"
azd env set IMAGEGEN_DEPLOYMENT "gpt-image-1-5"
azd env set IMAGEGEN_15_DEPLOYMENT "gpt-image-1-5"
azd env set IMAGEGEN_1_MINI_DEPLOYMENT "gpt-image-1-mini"
azd env set SORA_DEPLOYMENT "sora"
```

### 3. Deploy Infrastructure
```bash
azd provision
```

### 4. Deploy Application
```bash
azd deploy
```

## Architecture

The deployment creates:

- **Azure AI Foundry** (AIServices): Unified AI resource with all model deployments
- **AI Foundry Project**: Scoped workspace for the application
- **Azure Container Apps Environment**: Serverless container hosting
- **Backend Container App**: FastAPI application (Python) with SystemAssigned managed identity
- **Frontend Container App**: Next.js application (Node.js)
- **Azure Container Registry**: Private registry for storing Docker images
- **Azure Storage Account**: For storing generated images and videos
- **Azure Cosmos DB**: For metadata storage
- **Log Analytics Workspace**: For monitoring and logging

### RBAC Role Assignments (auto-provisioned)

| Principal | Role | Scope |
|-----------|------|-------|
| Backend Container App | Cognitive Services OpenAI User | AI Foundry |
| Backend Container App | Storage Blob Data Contributor | Storage Account |
| Backend Container App | Storage Blob Delegator | Storage Account |
| Backend Container App | Cosmos DB Data Contributor | Cosmos DB Account |

## Environment Variables

The following environment variables are automatically configured by the infrastructure:

### Backend
- `AI_FOUNDRY_ENDPOINT`: AI Foundry endpoint URL
- `LLM_DEPLOYMENT`: LLM deployment name
- `IMAGEGEN_DEPLOYMENT`: Image generation deployment name
- `IMAGEGEN_15_DEPLOYMENT`: GPT-Image-1.5 deployment name
- `IMAGEGEN_1_MINI_DEPLOYMENT`: GPT-Image-1-mini deployment name
- `SORA_DEPLOYMENT`: Sora deployment name
- `AZURE_BLOB_SERVICE_URL`: Storage endpoint URL
- `AZURE_STORAGE_ACCOUNT_NAME`: Storage account name
- `AZURE_BLOB_IMAGE_CONTAINER`: Container for images (default: "images")
- `AZURE_COSMOS_DB_ENDPOINT`: Cosmos DB endpoint
- `AZURE_COSMOS_DB_ID`: Database name
- `AZURE_COSMOS_CONTAINER_ID`: Container name

## Local Development

For local development, the app uses `DefaultAzureCredential` which picks up your Azure CLI credentials:

```bash
# Login to Azure (required for local development)
az login

# Set environment variables in .env (see .env.example)
cp .env.example .env
# Edit .env with your AI Foundry endpoint and deployment names

# Run the backend
cd backend && uvicorn main:app --reload
```

## Monitoring

Access your deployment logs and metrics:

```bash
# View application logs
azd logs

# Monitor resources in Azure Portal
azd show --output table
```

## Cleanup

To remove all Azure resources:

```bash
azd down
```

## Troubleshooting

### Common Issues

1. **Credential errors locally**: Run `az login` to authenticate. `DefaultAzureCredential` requires an active Azure CLI session.
2. **RBAC propagation delay**: After initial deployment, role assignments may take 1-5 minutes to propagate. If the app shows 403 errors on first start, wait and restart.
3. **Region availability**: Some models (Sora, GPT-Image) may not be available in all regions. Default is `swedencentral`.
4. **Permission Issues**: You need Owner role on the resource group to create RBAC assignments.

### Getting Help

```bash
# Check azd status
azd env list

# View detailed logs
azd logs --follow

# Get environment info
azd env get-values
```

For more information, see the [Azure Developer CLI documentation](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/).
