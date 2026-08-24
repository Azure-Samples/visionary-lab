# Backend Documentation

This document provides an overview of the backend system for the AI Content Lab. It is intended to help developers, including future AI systems, understand the project structure, design decisions, and how to navigate the codebase.

## 1. Introduction

The backend is a FastAPI application responsible for handling API requests, processing data, interacting with AI models (such as OpenAI's GPT-Image-1 and Sora), managing storage (Azure Blob Storage), and serving data to the frontend or other clients.

## 2. Project Structure

The backend codebase is organized into several key directories:

```
backend/
├── .dockerignore        # Specifies intentionally untracked files for Docker
├── .env                 # Environment variables (local, not committed)
├── Dockerfile           # Instructions to build the Docker image
├── __init__.py
├── main.py              # FastAPI application entry point
├── worker.py            # Standalone durable image-job worker entry point
├── jobs/                # Queue, Cosmos store, dispatcher, and worker lifecycle
├── api/                 # API endpoint definitions
│   ├── __init__.py
│   └── endpoints/       # Routers for different API resources
│       ├── __init__.py
│       ├── env.py       # Environment-related endpoints (e.g., config)
│       ├── gallery.py   # Gallery-related API endpoints
│       ├── images.py    # Image generation and management endpoints
│       └── videos.py    # Video generation and management endpoints
├── core/                # Core business logic, services, and utilities
│   ├── __init__.py
│   ├── analyze.py       # Modules for content analysis
│   ├── azure_storage.py # Client for Azure Blob Storage interaction
│   ├── config.py        # Application configuration settings
│   ├── gpt_image.py     # Logic for OpenAI GPT-Image-1 API
│   ├── resources.py     # Lazy process-owned AI clients and shutdown
│   ├── sas.py           # Renewable on-demand browser SAS tokens
│   ├── instructions.py  # Handling instructions/prompts for AI models
│   ├── sora.py          # Logic for OpenAI Sora video generation API
│   └── storage.py       # Abstraction layer for storage operations
├── models/              # Pydantic models for data validation and serialization
│   ├── __init__.py
│   ├── common.py        # Common/shared Pydantic models
│   ├── gallery.py       # Pydantic models for gallery features
│   ├── images.py        # Pydantic models for image generation/data
│   ├── image_jobs.py    # Batch, output-slot, progress, and retry contracts
│   └── videos.py        # Pydantic models for video generation/data
└── static/              # Static files (if any, served by the backend)
```

### Key Files and Directories:

*   **`main.py`**: FastAPI API entry point. In production it opens the durable store/queue but does not consume image work.
*   **`worker.py`**: No-ingress process that consumes Azure Storage Queue messages and owns long-running generation pipelines.
*   **`jobs/`**: Implements idempotent submission, outbox reconciliation, leases, cancellation, retries/dead-lettering, and progressive per-image outputs.
*   **`api/`**: This directory contains all API-related code.
    *   **`api/endpoints/`**: Each file in this subdirectory typically defines a FastAPI `APIRouter` for a specific resource or functionality (e.g., `images.py` for image-related endpoints, `videos.py` for video-related endpoints). This is the first place to look when trying to understand or modify an API endpoint.
*   **`core/`**: This directory houses the core business logic of the application.
    *   **`config.py`**: Manages application settings, often loaded from environment variables.
    *   **`gpt_image.py`**: Contains all logic related to interacting with the OpenAI GPT-Image-1 model. This includes handling API parameters, processing responses, and managing features like transparency and metadata.
    *   **`sora.py`**: Contains logic for interacting with OpenAI's Sora video generation model for video generation capabilities.
    *   **`azure_storage.py`**: Implements the client for interacting with Azure Blob Storage, used for saving generated images and videos.
    *   **`storage.py`**: May act as an abstraction layer over different storage solutions, currently utilizing `azure_storage.py`.
    *   **`instructions.py`**: Handles the parsing, validation, and transformation of user prompts/instructions before sending them to AI models.
    *   **`analyze.py`**: For tasks related to analyzing content (images, videos, text).
*   **`models/`**: Contains Pydantic models that define the structure of API request and response bodies, as well as internal data structures. These models are crucial for data validation and serialization.
    *   Files like `images.py`, `videos.py`, and `gallery.py` contain models specific to those resources. For example, `models/images.py` contains models like `ImageGenerateRequest`, `ImageSaveRequest`, and `ImageGenerationResponse`.
*   **`Dockerfile` and `.dockerignore`**: Used for building a Docker container for the backend, facilitating deployment and ensuring a consistent runtime environment.
*   **`.env`**: Used locally to store environment variables. This file should not be committed to version control.

## 3. Key Design Decisions & Conventions

### Durable image jobs

Image generation does not use FastAPI `BackgroundTasks`. FastAPI recommends a
real queue/worker system for heavy work that must survive multiple processes or
servers, while application lifespan is reserved for owning process-local
resources and supervised tasks:

- [FastAPI concurrency and async I/O](https://fastapi.tiangolo.com/async/)
- [FastAPI BackgroundTasks caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [Azure Container Apps scaling](https://learn.microsoft.com/azure/container-apps/scale-app)

The API persists a Cosmos job/outbox record and dispatches only a job ID to
Azure Storage Queue. A separate no-ingress Container App consumes messages,
renews leases, publishes per-output progress, and can scale to zero. This keeps
HTTP and model capacity independent and makes API restarts harmless to running
jobs.

*   **Multiple AI Services Integration**: The backend integrates with multiple OpenAI services:
    * **Sora** for video generation
    * **GPT-Image-1** for image generation
    * **LLM (Large Language Model)** for text processing and analysis

*   **API Documentation**: The backend automatically generates OpenAPI documentation available at `/api/v1/openapi.json`. This provides a comprehensive reference for all API endpoints, request/response models, and available operations.

*   **FastAPI Framework**: The backend leverages the FastAPI framework, chosen for its high performance, asynchronous capabilities, automatic data validation (via Pydantic), and built-in OpenAPI/Swagger documentation.
*   **Modular Design**: The codebase is structured modularly, separating concerns into `api` (presentation layer), `core` (business logic/services), and `models` (data structures). This promotes maintainability and scalability.
*   **Service-Oriented Logic**: Complex operations and interactions with external services (like OpenAI APIs or Azure Storage) are encapsulated within service modules in the `core/` directory (e.g., `core/gpt_image.py`, `core/azure_storage.py`). API endpoints in `api/endpoints/` then utilize these services.
*   **Pydantic for Data Validation**: All incoming API request data and outgoing responses are validated using Pydantic models defined in the `models/` directory. This ensures data integrity and provides clear API contracts.
*   **Configuration Management**: Application settings are managed centrally in `core/config.py` and are loaded from environment variables (defined in the parent `.env` file), allowing for different configurations across environments (dev, staging, prod). The configuration includes:
    * API settings with versioning (`API_V1_STR`)
    * AI model provider configuration (Azure/OpenAI)
    * Service-specific settings for Sora, LLM, and GPT-Image-1
    * Azure Blob Storage configuration with multiple authentication options
    * Default parameters for image generation (size, quality, format)
*   **AI Model Integration (`gpt_image.py`, `sora.py`)**:
    *   `core/__init__.py` has no network side effects. SDK clients are created lazily through `core/resources.py`, warmed from application/worker lifespan, and closed on shutdown.
    *   Specific modules are dedicated to each AI service to encapsulate their unique APIs and data handling requirements.
    *   **Flexible API Response Handling**: The system is designed to robustly handle variations in OpenAI API response structures, especially for usage information. This involves checking if usage is a dict or an object, using `getattr()` with default values to safely access attributes, wrapping usage processing in try/except blocks, and including proper logging for debugging response structure issues.
    *   **Parameter Support**: The backend supports parameters for AI models including `model`, `prompt`, `n`, `size`, `quality`, and `user`. For image editing, it additionally supports `image` and `mask` parameters. The backend also includes models for parameters not yet supported by the client (like `output_format`, `output_compression`, `background`, and `moderation`) for future compatibility.
    *   **Image Processing**: For GPT-Image-1, features like transparent background detection, preservation (saving as PNG if transparent), and metadata handling for quality, size, and format are implemented. The system detects if an image has an alpha channel, ensures transparent images are saved as PNG, adds transparency information to metadata, and uses the requested output format when appropriate.
    *   **Token Usage Tracking**: Metadata includes token usage for AI API calls, allowing for monitoring and potentially billing based on API usage.
*   **Cloud Storage (Azure Blob Storage)**:
    *   Generated artifacts (images, videos) are stored in Azure Blob Storage.
    *   The system supports two authentication methods:
        * Connection string (deprecated)
        * Individual credential components (account name, key, service URL)
    *   Separate containers are defined for images (`AZURE_BLOB_IMAGE_CONTAINER`) and videos (`AZURE_BLOB_VIDEO_CONTAINER`)
    *   The `core/azure_storage.py` module handles direct interactions with Azure, while `core/storage.py` provides a higher-level abstraction.
*   **Asynchronous Operations**: Provider, Blob, Queue, and job-state calls use native async SDKs. The HTTP API returns `202 Accepted`; durable work runs outside the API in queue-scaled workers. Remaining synchronous metadata boundaries are isolated with `asyncio.to_thread()` and reused for the worker lifetime.
*   **Testing Approach**: Unit and contract tests live in `tests/`, including concurrent workers, output progress, dispatch-gap repair, cancellation races, dead-lettering, native async SDK use, and partial saves. Azure integration tests are marked `integration`.

## 4. Directory Structure Details

*   **Storage Directories**: The application creates and uses several directories for local storage (defined in `config.py`):
    *   **UPLOAD_DIR**: `./static/uploads` - For temporary uploads
    *   **IMAGE_DIR**: `./static/images` - For storing generated/processed images
    *   **VIDEO_DIR**: `./static/videos` - For storing generated/processed videos
    
    These directories are automatically created at startup in `main.py` if they don't exist.

*   **API Endpoints**: The backend implements numerous endpoints for different operations:
    *   **Images**: Generation, editing, analysis, prompt enhancement, brand protection, and file management
    *   **Videos**: Generation, management, and processing
    *   **Gallery**: Managing collections of generated content
    *   **Environment**: Configuration and environment information

## 5. How to Find Information

*   **To understand an API endpoint (e.g., how to generate an image)**:
    1.  Start by looking in `backend/api/endpoints/`. For image generation, `images.py` is the relevant file.
    2.  Identify the specific route (e.g., `/images/generate`).
    3.  Examine the request model (from `backend/models/images.py`) to see expected input.
    4.  Trace the function calls into `backend/core/` (e.g., `core/gpt_image.py`) to understand the underlying business logic.
*   **To understand how AI models are called (e.g., parameters for GPT-Image-1)**:
    1.  Go to `backend/core/`. For GPT-Image-1, look at `gpt_image.py`.
    2.  Check the functions that make calls to the OpenAI client.
    3.  Look at the implementation of methods like `generate_images` and `edit_image` to understand parameter handling and how API responses are processed.
*   **To find data structures (request/response schemas)**:
    1.  Navigate to `backend/models/`.
    2.  Files are named after the resource they model (e.g., `images.py` for image-related Pydantic models like `ImageGenerateRequest`, `ImageSaveRequest`).
*   **To understand configuration settings**:
    1.  Look at `backend/core/config.py`.
*   **To understand storage operations (e.g., how images are saved to Azure)**:
    1.  Check `backend/core/storage.py` for the abstraction layer.
    2.  Dive into `backend/core/azure_storage.py` for the Azure-specific implementation.
*   **To understand the application's entry point and overall setup**:
    1.  Review `backend/main.py`.

## 6. Development Guidelines for Future AI Systems

When developing new features or modifying existing ones, please adhere to the following:

*   **Maintain Modularity**: Continue to separate concerns. Place API endpoint definitions in `api/endpoints/`, business logic in `core/`, and Pydantic models in `models/`.
*   **Follow Existing Patterns**: When adding new AI model integrations, create a dedicated service module in `core/` (e.g., `core/new_ai_model.py`). Define corresponding Pydantic models in `models/` and API endpoints in `api/endpoints/`.
*   **Use Pydantic Models**: For all new API request/response bodies and significant internal data structures, define Pydantic models to ensure validation and clarity.
*   **Prioritize Asynchronous Code**: For I/O-bound operations, use `async` and `await` to maintain application responsiveness.
*   **Configuration**: Add new configuration variables to `core/config.py` and ensure they can be set via environment variables.
*   **Error Handling**: Implement robust error handling, especially for external API calls and I/O operations. Provide meaningful error messages.
*   **Logging**: Add appropriate logging to help with debugging and monitoring.
*   **Testing Recommendations**: When adding new features, consider writing unit and integration tests. For external dependencies like OpenAI API and Azure Blob Storage, use mocks to ensure tests are reliable and reproducible without making actual API calls or storage operations.
*   **Document Design Decisions**: Document important architectural decisions, implementation details, and learnings directly in the codebase (using docstrings) and in this document. This helps maintain context for future development.
*   **Update This Document**: If significant structural changes or new architectural patterns are introduced, please update this `BACKEND.MD` file accordingly.

By following these guidelines, we can ensure the backend remains maintainable, scalable, and easy to understand for all contributors, including AI-driven development systems.
