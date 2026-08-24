# Backend Documentation

The backend is a FastAPI application for generating, analyzing, storing, and organizing images. It integrates with OpenAI image and language models, Azure Blob Storage, and Azure Cosmos DB.

## Project structure

```text
backend/
├── main.py
├── worker.py
├── jobs/
│   ├── factory.py
│   ├── manager.py
│   ├── queue.py
│   └── store.py
├── api/endpoints/
│   ├── env.py
│   ├── gallery.py
│   ├── image_jobs.py
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

- `main.py` creates the API application and owns API-side durable job clients during its lifespan.
- `worker.py` is the standalone no-ingress process that consumes durable image jobs.
- `jobs/` implements queue dispatch, Cosmos persistence, leases, cancellation, retries, and worker lifecycle.
- `api/endpoints/image_jobs.py` exposes submission, status, cancellation, and retry endpoints.
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
- Durable image-job queue, worker, retry, and retention settings

`main.py` creates the configured upload and image directories at startup. The generated OpenAPI schema is available at `/api/v1/openapi.json`.

## Durable image jobs

Long-running generation is accepted through the image-job API and dispatched to a queue-backed worker; it does not run as a FastAPI `BackgroundTask`. In Azure, the API and worker use the same image with different `IMAGE_JOB_ROLE` values. Locally, `IMAGE_JOB_ROLE=all` keeps both roles in one process while retaining the same durable interfaces.

Production uses Azure Storage Queue and Cosmos DB with managed identity. The worker owns generation, progress reporting, cancellation, lease renewal, poison-message handling, and progressive image-output persistence. Application lifespan opens and closes process-owned SDK clients explicitly so importing backend modules does not perform network I/O.

## Design conventions

- Keep endpoint definitions in `api/endpoints/`, service logic in `core/`, and API contracts in `models/`.
- Use Pydantic models for request and response validation.
- Keep I/O-bound request paths asynchronous; move blocking SDK operations to worker threads when needed.
- Treat Cosmos DB as the gallery metadata source of truth and Azure Blob Storage as the image binary store.
- Use dependency injection around external services so tests can replace them with mocks.
- Add configuration through `core/config.py` and document new required environment variables.

## Tests

Tests live in the repository-level `tests/` directory. Unit tests mock external services; integration tests use configured Azure credentials and are marked `integration`.
