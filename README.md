# Visionary Lab

**Create high-quality visual content with the gpt-image-1 model on Azure OpenAI—tailored for professional use cases.**

## Key Features

- Generate polished image assets from text prompts, input images, or both
- Refine prompts using AI best practices to ensure high-impact visuals
- Analyze outputs with AI for quality control, metadata tagging, and asset optimization
- Manage your content in an organized asset library

<img src="ui-sample.png" alt="description" width="800"/>

> Note: You can also use the [notebook](notebooks/gpt-image-1.ipynb) if you want to explore gpt-image-1 using the API.

## Prerequisites

Azure resources:

- Azure OpenAI resource with deployed `gpt-image-1` model
- Azure OpenAI `gpt-4.1` model deployment (used for prompt enhancements and image analysis)
- Azure Storage Account with a Blob Container for your images. You can use virtual folders to organize your content.

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
cd backend
cp .env.example .env
```

The environment variables will be defined below.

#### 3. Frontend Setup

##### 3.1 Navigate to the Frontend Directory

```bash
cd frontend
```

##### 3.2 Install Dependencies

```bash
npm install --legacy-peer-deps
```

## Step 2: Configure Resources

1. Configure Azure credentials in the backend:

   ```bash
   code backend/.env
   ```

   Replace the placeholders with your actual Azure values:

   - `IMAGEGEN_AOAI_RESOURCE`: name of the Azure OpenAI resource used for the gpt-image-1 deployment
   - `IMAGEGEN_DEPLOYMENT`: deployment name for the gpt-image-1 model
   - `IMAGEGEN_AOAI_API_KEY`
   - `LLM_AOAI_RESOURCE`: name of the Azure OpenAI resource used for the GPT-4.1 deployment
   - `LLM_DEPLOYMENT`: deployment name for the GPT-4.1 model
   - `LLM_AOAI_API_KEY`
   - `AZURE_BLOB_SERVICE_URL`
   - `AZURE_STORAGE_ACCOUNT_NAME`
   - `AZURE_STORAGE_ACCOUNT_KEY`
   - `AZURE_BLOB_IMAGE_CONTAINER`

2. Configure your Storage Account in the frontend:
   ```bash
   code frontend/next.config.ts
   ```
   Replace `<storage-account-name>` with your actual Azure storage account name.

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
   npm run dev
   ```

   The frontend will be available at http://localhost:3000.

   In Codespaces, both the backend and frontend will be available via forwarded URLs that GitHub Codespaces provides.
