# Azure Deployment with Azure Developer CLI (azd)

This guide shows how to deploy the Visionary Lab to Azure using the Azure Developer CLI for one-click deployments.

## Prerequisites

- [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) installed
- Azure subscription with access to:
  - Azure Container Apps
  - Azure OpenAI Service (with GPT-4o, DALL-E 3, and Sora deployments)
  - Azure Storage Account
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
   When prompted by `azd up`, provide your Azure OpenAI service details in this order:
   
   **LLM Configuration:**
   - **LLM_AOAI_RESOURCE**: Your Azure OpenAI resource name for LLM
   - **LLM_DEPLOYMENT**: Your GPT deployment name (e.g., "gpt-4.1")
   - **LLM_AOAI_API_KEY**: Your LLM API key
   
   **Image Generation Configuration:**
   - **IMAGEGEN_AOAI_RESOURCE**: Your Azure OpenAI resource name for image generation
   - **IMAGEGEN_DEPLOYMENT**: Your image generation deployment name (e.g., "gpt-image-1")
   - **IMAGEGEN_AOAI_API_KEY**: Your image generation API key
   
   **Sora Configuration:**
   - **SORA_AOAI_RESOURCE**: Your Azure OpenAI resource name for Sora
   - **SORA_DEPLOYMENT**: Your Sora deployment name (e.g., "sora")
   - **SORA_AOAI_API_KEY**: Your Sora API key

That's it! The `azd up` command will:
- Create a new environment
- Prompt for required Azure OpenAI configuration (resource names, deployments, API keys)
- Provision all Azure resources (Container Registry, Container Apps, Storage, etc.)
- Build Docker images for frontend and backend
- Push images to your private Azure Container Registry
- Deploy both services to Azure Container Apps
- Configure networking, authentication, and environment variables
- Provide you with the application URLs

## Manual Steps

If you prefer manual control over the deployment process:

### 1. Initialize Environment
```bash
azd env new <environment-name>
```

### 2. Configure Environment Variables
Set your Azure OpenAI service details:
```bash
# LLM OpenAI
azd env set LLM_AOAI_RESOURCE "your-openai-resource-name"
azd env set LLM_DEPLOYMENT "gpt-4.1"
azd env set LLM_AOAI_API_KEY "your-gpt-key"

# Image Generation OpenAI
azd env set IMAGEGEN_AOAI_RESOURCE "your-openai-resource-name"
azd env set IMAGEGEN_DEPLOYMENT "gpt-image-1"
azd env set IMAGEGEN_AOAI_API_KEY "your-image-gen-key"

# Sora OpenAI
azd env set SORA_AOAI_RESOURCE "your-openai-resource-name"
azd env set SORA_DEPLOYMENT "sora"
azd env set SORA_AOAI_API_KEY "your-sora-key"
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

- **Azure Container Apps Environment**: Serverless container hosting
- **Backend Container App**: FastAPI application (Python)
- **Frontend Container App**: Next.js application (Node.js)
- **Azure Container Registry**: Private registry for storing Docker images
- **Azure Storage Account**: For storing generated images and videos
- **Log Analytics Workspace**: For monitoring and logging

## Environment Variables

The following environment variables are automatically configured:

### Backend & Frontend
- `AZURE_STORAGE_ACCOUNT_NAME`: Auto-generated storage account
- `AZURE_BLOB_SERVICE_URL`: Storage endpoint URL
- `AZURE_STORAGE_ACCOUNT_KEY`: Storage access key
- `AZURE_BLOB_IMAGE_CONTAINER`: Container for images (default: "images")
- `AZURE_CONTAINER_REGISTRY_ENDPOINT`: Container registry login server

### AI Services (All Configurable)
**LLM Configuration:**
- `LLM_AOAI_RESOURCE`: LLM OpenAI resource name
- `LLM_DEPLOYMENT`: LLM deployment name
- `LLM_AOAI_API_KEY`: LLM API key

**Image Generation Configuration:**
- `IMAGEGEN_AOAI_RESOURCE`: Image generation OpenAI resource name
- `IMAGEGEN_DEPLOYMENT`: Image generation deployment name
- `IMAGEGEN_AOAI_API_KEY`: Image generation API key

**Sora Configuration:**
- `SORA_AOAI_RESOURCE`: Sora OpenAI resource name
- `SORA_DEPLOYMENT`: Sora deployment name
- `SORA_AOAI_API_KEY`: Sora API key

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

1. **Missing OpenAI Resources**: Ensure you have created Azure OpenAI resources with the required model deployments
2. **Permission Issues**: Verify your Azure account has Contributor access to the subscription
3. **Region Availability**: Some OpenAI models may not be available in all regions

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
