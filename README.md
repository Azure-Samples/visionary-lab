# Visionary Lab

**Create high-quality visual content with GPT-Image-1.5, FLUX Kontext Pro, and Sora 2 on Azure AI Foundry — tailored for professional use cases.**

## Key Features

### Video Generation (Sora 2)
- Create videos from text prompts with the **Sora 2** model
- Generate videos from text + images (image-to-video)
- Audio automatically included in all generated videos
- Support for multiple resolutions: 720p and 1080p (landscape and portrait)
- Durations: 4s, 8s, or 12s

### Image Generation (GPT-Image-1.5 · FLUX Kontext Pro · GPT-Image-1-Mini)
- Generate polished image assets from text prompts, input images, or both
- **GPT-Image-1.5**: OpenAI's latest image model with face preservation and high-quality editing
- **FLUX Kontext Pro**: Black Forest Labs model for fast, high-fidelity image generation
- **GPT-Image-1-Mini**: Lightweight model for rapid prototyping
- Refine prompts using AI best practices to ensure high-impact visuals
- Analyze outputs with AI for quality control, metadata tagging, and asset optimization
- Guardrails for content showing brand products (brand protection)
- Durable, cancellable image batches with per-image progress and partial-result retry
- Generate several batches concurrently while continuing to compose new prompts

### Asset Management
- Manage your content in an organized asset library with folder support
- Automatic video analysis and metadata tagging

<img src="ui-sample.png" alt="Visionary Lab UI" width="800"/>

> You can also get started with our notebooks to explore the models and APIs:
>
> - Image generation: [gpt-image-1.ipynb](notebooks/gpt-image-1.ipynb)
> - Video generation: [sora-api-starter.ipynb](notebooks/sora-api-starter.ipynb)

## Architecture

Visionary Lab uses **Azure AI Foundry** as a single unified AI resource with all model deployments, and **managed identity** for all service connections (no API keys).

| Component | Service | Auth |
|-----------|---------|------|
| AI Models | Azure AI Foundry (AIServices) | Managed Identity |
| Image/Video Storage | Azure Blob Storage | Managed Identity |
| Image Job Dispatch | Azure Storage Queue | Managed Identity |
| Image Workers | Azure Container Apps (scale to zero) | Managed Identity |
| Metadata | Azure Cosmos DB | Managed Identity |
| Hosting | Azure Container Apps | SystemAssigned MI |

### Supported Model Deployments

| Deployment | Model | Purpose |
|-----------|-------|---------|
| `gpt-4o` | GPT-4o | LLM for prompt enhancement and analysis |
| `gpt-image-1.5` | GPT-Image-1.5 | Primary image generation |
| `gpt-image-1-mini` | GPT-Image-1-Mini | Fast image generation |
| `flux-kontext-pro` | FLUX.1-Kontext-pro | Alternative image generation |
| `sora-2` | Sora 2 | Video generation |

## Prerequisites

Azure resources:

- Azure AI Foundry resource with deployed models (see table above)
- Azure Storage Account with Blob containers and an image-generation job queue
- Azure Cosmos DB account

Compute environment:

- Python 3.13+
- Node.js 22+ and npm
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
npm ci --registry=https://packagefeedproxy.microsoft.io/npm/
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
   | `SORA_DEPLOYMENT` | Video model deployment (e.g., `sora-2`) |
   | `AZURE_BLOB_SERVICE_URL` | Blob Storage URL |
   | `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name |
   | `AZURE_STORAGE_QUEUE_URL` | Storage Queue service URL |
   | `AZURE_STORAGE_QUEUE_NAME` | Durable image job queue |
   | `AZURE_STORAGE_POISON_QUEUE_NAME` | Terminal-failure diagnostics queue |
   | `AZURE_COSMOS_DB_ENDPOINT` | Cosmos DB endpoint URL |

   > **No API keys needed.** All services authenticate via `DefaultAzureCredential` which uses your `az login` session locally and managed identity in Azure.

> **Note:** For the best experience, deploy all models. The app works with a subset — unavailable models are gracefully skipped.

### Sora 2 Specifications

**Supported Resolutions:**
- 1280×720 (16:9 landscape)
- 720×1280 (9:16 portrait)
- 1792×1024 (16:9 landscape, high quality)
- 1024×1792 (9:16 portrait, high quality)

**Supported Durations:** 4s, 8s, or 12s

**Audio:** All generated videos automatically include synchronized audio

## Step 3: Running the Application

1. Start the local stack:

   ```bash
   ./scripts/dev.sh
   ```

   The backend runs on http://localhost:8000 and the frontend on
   http://localhost:3000. Local mode runs the API and queue consumers in one
   process; Azure deploys them independently.

   **Note:**
   If you encounter: `ImportError: libGL.so.1: cannot open shared object file`, install:
   ```bash
   sudo apt update && sudo apt install libgl1-mesa-glx
   ```

2. To run either side independently:

   ```bash
   UV_CACHE_DIR=.uv-cache uv run fastapi dev backend/main.py --port 8000
   cd frontend && npm run dev
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
- **Model deployment names**: Which models to deploy (gpt-4o, gpt-image-1.5, sora-2, etc.)

✨ That's it! Your Visionary Lab will be running on Azure Container Apps with:
- Azure AI Foundry with all model deployments
- Managed identity for all service connections (no API keys)
- Azure Storage and Cosmos DB for content management
- A private FastAPI API app plus a no-ingress, queue-scaled image worker app
- RBAC role assignments auto-configured
- Optional Entra ID authentication (configurable per deployment)

📖 For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)
