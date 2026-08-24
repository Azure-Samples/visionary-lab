# Visionary Lab

**Create high-quality image content with GPT-Image-1.5, FLUX Kontext Pro, and GPT-Image-1-Mini on Azure AI Foundry — tailored for professional use cases.**

## Key Features

### Image Generation (GPT-Image-1.5 · FLUX Kontext Pro · GPT-Image-1-Mini)
- Generate polished image assets from text prompts, input images, or both
- **GPT-Image-1.5**: OpenAI's latest image model with face preservation and high-quality editing
- **FLUX Kontext Pro**: Black Forest Labs model for fast, high-fidelity image generation
- **GPT-Image-1-Mini**: Lightweight model for rapid prototyping
- Refine prompts using AI best practices to ensure high-impact visuals
- Analyze outputs with AI for quality control, metadata tagging, and asset optimization
- Guardrails for content showing brand products (brand protection)

### Asset Management
- Manage your content in an organized asset library with folder support
- Automatic image analysis and metadata tagging

> You can also get started with our notebooks to explore the models and APIs:
>
> - Image generation: [gpt-image-1.ipynb](notebooks/gpt-image-1.ipynb)

## Architecture

Visionary Lab uses **Azure AI Foundry** as a single unified AI resource with all model deployments, and **managed identity** for all service connections (no API keys).

| Component | Service | Auth |
|-----------|---------|------|
| AI Models | Azure AI Foundry (AIServices) | Managed Identity |
| Image Storage | Azure Blob Storage | Managed Identity |
| Metadata | Azure Cosmos DB | Managed Identity |
| Hosting | Azure Container Apps | SystemAssigned MI |

### Supported Model Deployments

| Deployment | Model | Purpose |
|-----------|-------|---------|
| `gpt-4o` | GPT-4o | LLM for prompt enhancement and analysis |
| `gpt-image-1.5` | GPT-Image-1.5 | Primary image generation |
| `gpt-image-1-mini` | GPT-Image-1-Mini | Fast image generation |
| `flux-kontext-pro` | FLUX.1-Kontext-pro | Alternative image generation |

## Prerequisites

Azure resources:

- Azure AI Foundry resource with deployed models (see table above)
- Azure Storage Account with a Blob Container for images
- Azure Cosmos DB account

Compute environment:

- Python 3.12+
- Node.js 19+ and npm
- Git
- uv package manager
- Azure CLI (`az login` required for local development)

## Step 1: Installation (One-time)

### Option A: Quick Start with GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?hide_repo_select=true&ref=main&repo=Azure-Samples/visionary-lab)

Wait for the Codespace to initialize, then continue with [Step 2: Configure Resources](#step-2-configure-resources).

### Option B: Local Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/Azure-Samples/visionary-lab
```

#### 2. Backend Setup

##### 2.1 Install UV Package Manager

Mac/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

##### 2.2 Copy environment file template

```bash
cp .env.example .env
```

#### 3. Frontend Setup

```bash
cd frontend
npm install --legacy-peer-deps
```

## Step 2: Configure Resources

1. **Login to Azure** (required for managed identity authentication):

   ```bash
   az login
   ```

2. **Configure environment variables** in `.env`:

   ```bash
   code .env
   ```

   | Setting | Description |
   |---------|-------------|
   | `AI_FOUNDRY_ENDPOINT` | Your AI Foundry endpoint (e.g., `https://your-foundry.cognitiveservices.azure.com/`) |
   | `LLM_DEPLOYMENT` | LLM deployment name (e.g., `gpt-4o`) |
   | `IMAGEGEN_DEPLOYMENT` | Primary image model deployment (e.g., `gpt-image-1.5`) |
   | `IMAGEGEN_1_MINI_DEPLOYMENT` | Mini image model deployment (e.g., `gpt-image-1-mini`) |
   | `FLUX_KONTEXT_DEPLOYMENT` | FLUX model deployment (e.g., `flux-kontext-pro`) |
   | `AZURE_BLOB_SERVICE_URL` | Blob Storage URL |
   | `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name |
   | `AZURE_COSMOS_DB_ENDPOINT` | Cosmos DB endpoint URL |

   > **No API keys needed.** All services authenticate via `DefaultAzureCredential` which uses your `az login` session locally and managed identity in Azure.

> **Note:** The app works with a subset of the image models; unavailable deployments are gracefully skipped.

## Step 3: Running the Application

1. Start the backend:

   ```bash
   cd backend
   uv run fastapi dev
   ```

   The backend server will start on http://localhost:8000.

2. Open a new terminal to start the frontend:

   ```bash
   cd frontend
   npm run build
   npm start
   ```

   The frontend will be available at http://localhost:3000.

## 🚀 Deploy to Azure

For production deployment, use Azure Developer CLI:

**Prerequisites**: [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)

```bash
git clone https://github.com/Azure-Samples/visionary-lab
cd visionary-lab

azd auth login
azd up
```

During `azd up`, you'll be prompted for:
- **AI Foundry name**: Globally unique name for your AI Foundry resource
- **Model deployment names**: Which LLM and image models to deploy (for example, gpt-4o and gpt-image-1.5)

✨ That's it! Your Visionary Lab will be running on Azure Container Apps with:
- Azure AI Foundry with all model deployments
- Managed identity for all service connections (no API keys)
- Azure Storage and Cosmos DB for content management
- RBAC role assignments auto-configured
- Optional Entra ID authentication (configurable per deployment)

📖 For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)
