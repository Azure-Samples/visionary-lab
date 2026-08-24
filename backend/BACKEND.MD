# Backend Documentation

The backend is a FastAPI application for generating, analyzing, storing, and organizing images. It integrates with OpenAI image and language models, Azure Blob Storage, and Azure Cosmos DB.

## Project structure

```text
backend/
├── main.py
├── api/endpoints/
│   ├── env.py
│   ├── gallery.py
│   ├── images.py
│   └── metadata_router.py
├── core/
│   ├── analyze.py
│   ├── azure_storage.py
│   ├── config.py
│   ├── cosmos_client.py
│   ├── gpt_image.py
│   ├── image_pipeline.py
│   └── instructions.py
├── models/
│   ├── common.py
│   ├── gallery.py
│   ├── images.py
│   └── metadata_models.py
└── static/images/
```

## Main components

- `main.py` creates the application, middleware, static file mount, and API routers.
- `api/endpoints/images.py` exposes image generation, editing, analysis, prompt enhancement, and file-management endpoints.
- `api/endpoints/gallery.py` exposes the image gallery, uploads, folders, downloads, and storage access tokens.
- `api/endpoints/metadata_router.py` manages image metadata backed by Cosmos DB.
- `core/gpt_image.py` integrates with the image-generation provider.
- `core/image_pipeline.py` coordinates generation, analysis, and persistence workflows.
- `core/analyze.py` contains image analysis helpers.
- `core/azure_storage.py` stores images in the configured Azure Blob container.
- `core/cosmos_client.py` stores searchable image metadata and folder records.
- `core/config.py` loads application and service settings from the environment.
- `models/` contains the Pydantic request and response contracts.

## Configuration

The backend uses centralized settings from `core/config.py`, including:

- API name and version prefix
- Azure AI Foundry endpoint and model deployment names
- Azure Blob Storage account, service URL, CDN URL, and image container
- Azure Cosmos DB endpoint, database, and container
- Local upload and image directories
- Image-generation defaults

`main.py` creates the configured upload and image directories at startup. The generated OpenAPI schema is available at `/api/v1/openapi.json`.

## Design conventions

- Keep endpoint definitions in `api/endpoints/`, service logic in `core/`, and API contracts in `models/`.
- Use Pydantic models for request and response validation.
- Keep I/O-bound request paths asynchronous; move blocking SDK operations to worker threads when needed.
- Treat Cosmos DB as the gallery metadata source of truth and Azure Blob Storage as the image binary store.
- Use dependency injection around external services so tests can replace them with mocks.
- Add configuration through `core/config.py` and document new required environment variables.

## Tests

Tests live in the repository-level `tests/` directory. Unit tests mock external services; integration tests use configured Azure credentials and are marked `integration`.
