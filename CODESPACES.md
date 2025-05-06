# GitHub Codespaces Setup Guide

This document provides instructions for setting up and using Visionary Lab in GitHub Codespaces.

## Automatic Setup

When you create a new GitHub Codespace for this repository, the following will be automatically set up:

- Python 3.12 environment
- Node.js 19 
- System dependencies (including `libgl1-mesa-glx` for OpenCV)
- UV package manager
- Backend environment template file (`.env.example` → `.env`)
- Frontend dependencies

## Manual Configuration Steps

After your Codespace is created, you'll need to perform these manual configuration steps:

### 1. Configure Azure Credentials

Edit the backend environment file with your Azure credentials:

```bash
code backend/.env
```

Replace the following placeholders with your actual Azure values:
- `AOAI_RESOURCE`
- `AOAI_API_KEY`
- `AOAI_API_VERSION`
- `IMAGEGEN_DEPLOYMENT`
- `IMAGEGEN_AOAI_API_KEY`
- `AZURE_STORAGE_ACCOUNT`
- `AZURE_STORAGE_KEY`
- `AZURE_CONTAINER_NAME`

### 2. Configure Storage Account in Frontend

Update the next.config.ts file with your Azure storage account name:

```bash
code frontend/next.config.ts
```

Replace `<storage-account-name>` in the file with your actual Azure storage account name:

```typescript
{
  hostname: '<storage-account-name>.blob.core.windows.net',
}
```

## Running the Application

Once configured, you can start the application:

1. Start the backend:
   ```bash
   cd backend
   uv run fastapi dev
   ```

2. Start the frontend (in a new terminal):
   ```bash
   cd frontend
   npm run dev
   ```

## Accessing the Application

When running in Codespaces:

- The backend will be available at port 8000 - GitHub Codespaces will provide a URL
- The frontend will be available at port 3000 - GitHub Codespaces will provide a URL