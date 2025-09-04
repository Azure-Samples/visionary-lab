# Visionary Lab

**Create high-quality visual content with GPT-Image-1 and Sora on Azure OpenAI—tailored for professional use cases.**

## Key Features

- Create videos from a text prompt with the Sora model
- Generate polished image assets from text prompts, input images, or both
- Refine prompts using AI best practices to ensure high-impact visuals
- Analyze outputs with AI for quality control, metadata tagging, and asset optimization
- Provide guardrails for content showing brands products (brand protection)
- Manage your content in an organized asset library

<img src="ui-sample.png" alt="description" width="800"/>

> You can also get started with our notebooks to explore the models and APIs:
>
> - Image generation: [gpt-image-1.ipynb](notebooks/gpt-image-1.ipynb)
> - Video generation: [sora-api-starter.ipynb](notebooks/sora-api-starter.ipynb)

## Prerequisites

Azure resources:

- Azure OpenAI resource with a deployed `gpt-image-1` model
- Azure OpenAI resource with a deployed `Sora` model
- Azure OpenAI `gpt-4.1` model deployment (used for prompt enhancements and image analysis)
- Azure Storage Account with a Blob Container for your images and videos. You can use virtual folders to organize your content.

Compute environment:

- Python 3.12+
- Node.js 19+ and npm
- Git
- uv package manager
- Code editor (we are using VSCode in the instructions)

## Step 1: Installation (One-time)

### Option A: Quick Start with GitHub Codespaces

The quickest way to get started is using GitHub Codespaces, a hosted environment that is automatically set up for you. Click this button to create a Codespace (4-core machine recommended):

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?hide_repo_select=true&ref=main&repo=Azure-Samples/visionary-lab)

Wait for the Codespace to initialize. Python 3.12, Node.js 19, and dependencies will be automatically installed.

Now you can continue with [Step 2: Configure Resources.](#step-2-configure-resources)

### Option B: Local Installation on your device

#### 1. Clone the Repository

```bash
git clone https://github.com/Azure-Samples/visionary-lab
```

#### 2. Backend Setup

##### 2.1 Install UV Package Manager

UV is a fast Python package installer and resolver that we use for managing dependencies.

Mac/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (using PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

##### 2.2 Copy environment file template

```bash
cp .env.example .env
```

The environment variables will be defined below.

#### 3. Frontend Setup

```bash
cd frontend
npm install --legacy-peer-deps
```

## Step 2: Configure Resources

1. Configure Azure credentials using a code or text editor:

   ```bash
   code .env
   ```

   Replace the placeholders with your actual Azure values:

   | Service / Model   | Variables                                                                                                                                                                                                                                                                                                                                                                      |
   | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
   | **Sora**          | - `SORA_AOAI_RESOURCE`: name of the Azure OpenAI resource used for Sora <br> - `SORA_DEPLOYMENT`: deployment name for the Sora model <br> - `SORA_AOAI_API_KEY`: API key for the Azure OpenAI Sora resource                                                                                                                                                                    |
   | **GPT-Image-1**   | - `IMAGEGEN_AOAI_RESOURCE`: name of the Azure OpenAI resource used for gpt-image-1 <br> - `IMAGEGEN_DEPLOYMENT`: deployment name for the gpt-image-1 model <br> - `IMAGEGEN_AOAI_API_KEY`: API key for the gpt-image-1 resource                                                                                                                                                |
   | **GPT-4.1**       | - `LLM_AOAI_RESOURCE`: name of the Azure OpenAI resource used for GPT-4.1 <br> - `LLM_DEPLOYMENT`: deployment name for the GPT-4.1 model <br> - `LLM_AOAI_API_KEY`: API key for the GPT-4.1 resource                                                                                                                                                                           |
   | **Azure Storage** | - `AZURE_BLOB_SERVICE_URL`: URL to your Azure Blob Storage service <br> - `AZURE_STORAGE_ACCOUNT_NAME`: name of your Azure Storage Account <br> - `AZURE_STORAGE_ACCOUNT_KEY`: access key for your Azure Storage Account <br> - `AZURE_BLOB_IMAGE_CONTAINER`: name of the Blob Container for images <br> - `AZURE_BLOB_VIDEO_CONTAINER`: name of the Blob Container for videos |

> Note: For the best experience, use both Sora and GPT-Image-1. However, the app also works if you use only one of these models.

## Step 3: Running the Application

Once everything is set up:

1. Start the backend:

   ```bash
   cd backend
   uv run fastapi dev
   ```

   The backend server will start on http://localhost:8000. You can verify it's running by visiting http://localhost:8000/api/v1/health in your browser.

   **Note:**  
   If you encounter the error: `ImportError: libGL.so.1: cannot open shared object file: No such file or directory`, install the missing OpenCV library:

   ```bash
   sudo apt update
   sudo apt install libgl1-mesa-glx
   ```

   This step is not needed in Codespaces as it's automatically installed

2. Open a new terminal to start the frontend:

   ```bash
   cd frontend
   npm run build
   npm start
   ```

   The frontend will be available at http://localhost:3000.

## 🚀 Deploy to Azure

For production deployment, use Azure Developer CLI to deploy the entire application to Azure with one command:

**Prerequisites**: [Azure Developer CLI (azd)](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) installed

```bash
# Clone and deploy
git clone https://github.com/Azure-Samples/visionary-lab
cd visionary-lab

# Authenticate and deploy everything in one command
azd auth login
azd up
```

During `azd up`, you'll be prompted to configure your Azure OpenAI resources:
- **LLM Configuration**: Resource name, deployment name (e.g., "gpt-4.1"), and API key
- **Image Generation Configuration**: Resource name, deployment name (e.g., "gpt-image-1"), and API key
- **Sora Configuration**: Resource name, deployment name (e.g., "sora"), and API key

✨ That's it! Your Visionary Lab will be running on Azure Container Apps with:
- Azure Container Registry for Docker images
- Azure Storage for generated content
- Automatic scaling and monitoring

📖 For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)
