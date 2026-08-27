# Visionary Lab Project Structure

## Overview

Visionary Lab is an image generation, editing, analysis, and asset-management application. It combines a FastAPI backend with a Next.js frontend and uses Azure AI Foundry, Azure Blob Storage, and Azure Cosmos DB.

## Core Components

### Backend (Python)

- `backend/main.py`: FastAPI application entry point and router registration.
- `backend/api/endpoints/images.py`: Image generation, editing, analysis, and save operations.
- `backend/api/endpoints/gallery.py`: Image gallery, folder, upload, download, and deletion operations.
- `backend/api/endpoints/metadata_router.py`: Metadata synchronization and maintenance.
- `backend/api/endpoints/storylines.py`: Storyline creation, reference upload, plan review, progress, cancellation, retry, and regeneration.
- `backend/api/endpoints/env.py`: Environment configuration status.
- `backend/core/gpt_image.py`: Azure AI Foundry GPT-Image-2 client.
- `backend/core/image_pipeline.py`: Image workflow orchestration.
- `backend/core/storyline_planner.py`: Structured multi-image campaign planning.
- `backend/core/image_capabilities.py`: Provider capability discovery and validation.
- `backend/storylines/`: Persistent storyline state and durable frame coordination.
- `backend/core/analyze.py`: Image analysis with a multimodal language model.
- `backend/core/azure_storage.py`: Azure Blob Storage access.
- `backend/core/cosmos_client.py`: Azure Cosmos DB metadata access.
- `backend/models/`: Pydantic request and response models.

### Frontend (Next.js)

- `frontend/app/new-image/`: Image generation workflow and saved-image gallery.
- `frontend/components/storyline/`: Storyline composer, plan editor, persistent workspace, and comparison lanes.
- `frontend/app/edit-image/`: Image editing workflow.
- `frontend/app/analyze/`: Custom image analysis workflow.
- `frontend/app/settings/`: Application and model status.
- `frontend/components/`: Shared image and interface components.
- `frontend/context/`: Shared client-side state.
- `frontend/services/`: Backend API and storage URL clients.
- `frontend/utils/`: Image, gallery, date, and environment helpers.

### Infrastructure

- `infra/main.bicep`: Top-level Azure deployment.
- `infra/modules/`: Reusable modules for AI Foundry, Container Apps, Storage, Cosmos DB, networking, Front Door, and RBAC.
- `azure.yaml`: Azure Developer CLI service definitions.
- `docker-compose.yml`: Local multi-container setup.

### Notebook

- `notebooks/gpt-image-2.ipynb`: GPT-Image-2 generation and editing examples.
- `notebooks/utils.py`: Notebook image helpers.
- `notebooks/images/`: Sample input images.

## Main API Areas

- `/api/v1/images`: Generate, edit, save, and analyze images.
- `/api/v1/storylines`: Plan, persist, generate, reopen, cancel, retry, and regenerate storylines.
- `/api/v1/gallery/images`: List stored image assets.
- `/api/v1/gallery`: Manage image assets and folders.
- `/api/v1/metadata`: Synchronize and update asset metadata.
- `/api/v1/env/status`: Report required environment configuration.
- `/api/v1/health`: Report application health.

## Data Flow

1. A user starts an image workflow in the Next.js frontend.
2. The frontend sends the request to the FastAPI backend.
3. The backend calls the configured Azure AI Foundry deployment.
4. Generated images are stored in the image Blob container.
5. Searchable metadata is written to Cosmos DB.
6. The frontend retrieves the saved assets and metadata for display.

## Local Development

1. Copy `.env.example` to `.env` and configure the AI Foundry, Storage, and Cosmos DB values.
2. Authenticate locally with `az login`.
3. Start both services with `./scripts/dev.sh`, or run the backend and frontend separately.

Python dependencies are managed by `uv` from the repository root. Frontend dependencies are managed with npm in `frontend/`.
