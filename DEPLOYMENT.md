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
- **Backend API Container App**: FastAPI application (Python) with environment-internal ingress and no queue-based scaling
- **Image Worker Container App**: No-ingress queue consumer that scales independently from zero
- **Frontend Container App**: Next.js application (Node.js)
- **Azure Container Registry**: Private registry for storing Docker images
- **Azure Storage Account**: Blob storage for generated media and a durable image-generation job queue
- **Azure Cosmos DB**: For metadata storage
- **Log Analytics Workspace**: For monitoring and logging

### RBAC Role Assignments (auto-provisioned)

| Principal | Role | Scope |
|-----------|------|-------|
| Backend Container App | Cognitive Services OpenAI User | AI Foundry |
| Backend Container App | Storage Blob Data Contributor | Storage Account |
| Backend Container App | Storage Blob Delegator | Storage Account |
| Backend Container App | Storage Queue Data Contributor | Storage Account |
| Backend Container App | Cosmos DB Data Contributor | Cosmos DB Account |
| Image Worker Container App | Cognitive Services OpenAI User | AI Foundry |
| Image Worker Container App | Storage Blob Data Contributor | Storage Account |
| Image Worker Container App | Storage Blob Delegator | Storage Account |
| Image Worker Container App | Storage Queue Data Contributor | Storage Account |
| Image Worker Container App | Cosmos DB Data Contributor | Cosmos DB Account |
| Image Worker ACR identity | AcrPull | Azure Container Registry |

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
- `AZURE_STORAGE_QUEUE_URL`: Storage Queue service endpoint URL
- `AZURE_STORAGE_QUEUE_NAME`: Durable image job queue (default: "image-generation-jobs")
- `AZURE_STORAGE_POISON_QUEUE_NAME`: Failed-message diagnostics queue (default: "image-generation-jobs-poison")
- `CORS_ALLOWED_ORIGINS`: The deployed frontend origin and optional custom frontend domain
- `IMAGE_JOB_ROLE`: `api` on the web app and `worker` on the queue consumer
- `IMAGE_JOB_MODE`: Set to `azure` so production cannot silently fall back to process memory
- `IMAGE_JOB_CONCURRENCY`: Per-replica worker concurrency (worker only)
- `IMAGE_JOB_MAX_ATTEMPTS`: Maximum automatic worker attempts before dead-lettering
- `IMAGE_JOB_RETENTION_SECONDS`: Cosmos TTL for image job records (default: 30 days)
- `AZURE_COSMOS_DB_ENDPOINT`: Cosmos DB endpoint
- `AZURE_COSMOS_DB_ID`: Database name
- `AZURE_COSMOS_CONTAINER_ID`: Container name

The API and worker use separate system-assigned identities. The API keeps at least one replica for HTTP traffic, has environment-internal ingress, and has no queue scale rule. Browser traffic reaches it through the authenticated same-origin Next.js route at `BACKEND_URI`; service-to-service callers can use `BACKEND_INTERNAL_URI` from inside the Container Apps environment. The worker has no ingress or HTTP probe, can scale to zero, and scales only from the durable Storage Queue. Each worker gets 2 vCPU and 4 GiB memory; its queue-length target and per-replica concurrency are both two jobs by default, with up to 10 replicas. Override `imageGenerationQueueScaleTargetLength`, `imageWorkerConcurrency`, or `imageWorkerMaxReplicas` when provisioning if needed.

Blob CORS is provisioned declaratively rather than mutated by each worker. By default, the allowed origins are the generated frontend Container App URL plus `frontendCustomDomain` when configured. Advanced deployments can supply `storageBlobCorsAllowedOrigins` directly in Bicep to replace that list.

### Keeping the worker image synchronized

The API and worker run the same backend image with different `IMAGE_JOB_ROLE` values. Only the API carries the `azd-service-name: backend` host tag because azd requires exactly one host resource per service. A non-interactive backend `postdeploy` hook reads the image from the successfully deployed API revision and updates the worker to that exact image when needed. This runs for both `azd deploy backend` and the backend phase of `azd deploy`/`azd up`, and it fails the deployment if synchronization cannot be verified.

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
