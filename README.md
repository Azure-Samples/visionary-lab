# Visionary Lab

**Create and edit high-quality image content with GPT-Image-2 and FLUX Kontext Pro on Azure AI Foundry.**

## Key Features

### Image Generation (GPT-Image-2 · FLUX Kontext Pro)
- Generate polished image assets from text prompts, input images, or both
- **GPT-Image-2**: Default OpenAI image model for generation and high-fidelity editing
- **FLUX Kontext Pro**: Black Forest Labs model for fast, high-fidelity image generation
- Refine prompts using AI best practices to ensure high-impact visuals
- Analyze outputs with AI for quality control, metadata tagging, and asset optimization
- Guardrails for content showing brand products (brand protection)
- Durable, cancellable image batches with per-image progress and partial-result retry
- Generate several batches concurrently while continuing to compose new prompts

### Multi-image Storylines
- Build a persistent 2–10 frame campaign from text, one image, or several durable references
- Generate one shared creative direction with ordered frame purposes, prompts, and editable copy
- Start immediately or review, edit, add, remove, and reorder the plan before generation
- Compare the same frozen plan across every configured image model in ordered lanes
- Reuse stable visual anchors for continuity instead of chaining drift from frame to frame
- Track progressive completion, cancel an active storyline, retry an exact failed frame, or regenerate a frame with revised prompt and copy
- Use channel-aware copy depth and size suggestions without locking the image dimensions

### Asset Management
- Manage your content in an organized asset library with folder support
- Automatic image analysis and metadata tagging

> You can also get started with our notebooks to explore the models and APIs:
>
> - Image generation and editing: [gpt-image-2.ipynb](notebooks/gpt-image-2.ipynb)

## Architecture

Visionary Lab uses **Azure AI Foundry** as a single unified AI resource with all model deployments, and **managed identity** for all service connections (no API keys).

| Component | Service | Auth |
|-----------|---------|------|
| AI Models | Azure AI Foundry (AIServices) | Managed Identity |
| Image Storage | Azure Blob Storage | Managed Identity |
| Image Job Dispatch | Azure Storage Queue | Managed Identity |
| Image Workers | Azure Container Apps (scale to zero) | Managed Identity |
| Metadata | Azure Cosmos DB | Managed Identity |
| Hosting | Azure Container Apps | SystemAssigned MI |

### Supported Model Deployments

GPT-Image-2 is now the supported OpenAI image model for both generation and
editing. The previous GPT-Image-1, GPT-Image-1.5, and GPT-Image-1-Mini
deployments are no longer supported by this application.

| Deployment | Model | Purpose |
|-----------|-------|---------|
| `gpt-4o` | GPT-4o | LLM for prompt enhancement, analysis, and storyline planning |
| `gpt-image-2` | GPT-Image-2 | Default image generation and editing |
| `flux-kontext-pro` | FLUX.1-Kontext-pro | Alternative image generation |

## Prerequisites

Azure deployment resources:

- Azure AI Foundry resource with deployed models (see table above)
- Azure Storage Account with a Blob container for images and an image-generation job queue
- Azure Cosmos DB account

Compute environment:

- Python 3.13+
- Node.js 22+ and npm
- Git
- uv package manager
- Azure CLI (`az login` required for local development)
- Docker (used by `scripts/dev.sh` for the local Azurite Blob emulator)

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
   | `IMAGEGEN_2_DEPLOYMENT` | GPT-Image-2 deployment name (normally `gpt-image-2`) |
   | `FLUX_KONTEXT_DEPLOYMENT` | FLUX model deployment (e.g., `flux-kontext-pro`) |
   | `AZURE_STORAGE_CONNECTION_STRING` | `UseDevelopmentStorage=true` for the local Azurite Blob emulator; leave empty in Azure |
   | `AZURE_BLOB_SERVICE_URL` | Blob Storage URL |
   | `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name |
   | `AZURE_STORAGE_QUEUE_URL` | Storage Queue service URL |
   | `AZURE_STORAGE_QUEUE_NAME` | Durable image job queue |
   | `AZURE_STORAGE_POISON_QUEUE_NAME` | Terminal-failure diagnostics queue |
   | `AZURE_COSMOS_DB_ENDPOINT` | Cosmos DB endpoint URL |

   > **No Azure service API keys are needed.** `DefaultAzureCredential` uses your `az login` session for AI Foundry during host development and managed identity in Azure. The Azurite shortcut uses only the emulator's well-known local credentials.

   Local development defaults to `IMAGE_JOB_MODE=memory`. Set it to `azure`
   only when the configured Queue and Cosmos endpoints are reachable from your
   machine. With `AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true`,
   `scripts/dev.sh` starts a named Azurite Blob container and the backend creates
   the `images` container on first use.

## Step 3: Running the Application

1. Start the local stack:

   ```bash
   ./scripts/dev.sh
   ```

   The backend runs on http://localhost:8000 and the frontend on
   http://localhost:3000. Local mode runs the API and queue consumers in one
   process; Azure deploys them independently. If the development storage
   shortcut is configured, the script reuses an already-running
   `visionary-lab-azurite` container or starts and stops one with the stack.

2. To run either side independently:

   ```bash
   UV_CACHE_DIR=.uv-cache uv run fastapi dev backend/main.py --port 8000
   cd frontend && npm run dev
   ```

   The frontend will be available at http://localhost:3000.

   For GPT-Image-2 generation/editing tests that do not persist assets, use
   `./scripts/dev.sh --backend`; Blob, Queue, and Cosmos configuration is not
   required for that backend-only path.

## 🚀 Deploy to Azure

For production deployment, use Azure Developer CLI:

**Prerequisites**: [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd)

```bash
git clone https://github.com/Azure-Samples/visionary-lab
cd visionary-lab

azd auth login
azd up
```

During `azd up`, you'll be prompted for a globally unique AI Foundry name. The
template deploys the fixed application model set: `gpt-4o`, `gpt-image-2`, and
`flux-kontext-pro`.

✨ That's it! Your Visionary Lab will be running on Azure Container Apps with:
- Azure AI Foundry with all model deployments
- Managed identity for all service connections (no API keys)
- Azure Storage and Cosmos DB for content management
- A private FastAPI API app plus a no-ingress, queue-scaled image worker app
- RBAC role assignments auto-configured
- Optional Entra ID authentication (configurable per deployment)

📖 For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)
