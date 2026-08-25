# Docker Setup for Visionary Lab

Docker Compose runs the production-style backend and frontend images locally.
This Compose path uses Azure AI Foundry and Blob Storage through
`DefaultAzureCredential`; it does not use Azure OpenAI API keys or storage keys.
For the host-development Azurite flow, use `scripts/dev.sh` instead.

## Prerequisites

- Docker with the Compose plugin
- An Azure AI Foundry resource with `gpt-image-2` deployed
- Azure Blob Storage reachable from the Docker host
- Optional reachable Azure Queue and Cosmos DB endpoints when using durable jobs
- A Microsoft Entra service principal for the backend container

The host's `az login` session is not available inside a container. Configure the
standard Azure Identity environment variables `AZURE_CLIENT_ID`,
`AZURE_TENANT_ID`, and `AZURE_CLIENT_SECRET` for Docker Compose. In Azure,
Container Apps uses managed identity instead.

`AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true` is intentionally a
host-development setting: `scripts/dev.sh` starts Azurite at
`http://127.0.0.1:10000`. Clear it when using this Compose configuration and set
the Azure Blob URL and account name shown below.

## Configure `.env`

Copy the template and replace its placeholders:

```bash
cp .env.example .env
```

The relevant Compose settings are:

```env
MODEL_PROVIDER=azure
AI_FOUNDRY_ENDPOINT=https://your-foundry-name.cognitiveservices.azure.com/
LLM_DEPLOYMENT=gpt-4o
IMAGEGEN_2_DEPLOYMENT=gpt-image-2
FLUX_KONTEXT_DEPLOYMENT=flux-kontext-pro

AZURE_BLOB_SERVICE_URL=https://your-storage-account.blob.core.windows.net/
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_BLOB_IMAGE_CONTAINER=images

# Local queue/store mode. Use azure only with reachable Queue and Cosmos.
IMAGE_JOB_MODE=memory
AZURE_STORAGE_QUEUE_URL=
AZURE_COSMOS_DB_ENDPOINT=

# DefaultAzureCredential inside the backend container.
AZURE_CLIENT_ID=your-service-principal-client-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_SECRET=your-service-principal-secret
```

Grant the service principal the same data-plane roles used by the deployed
Container Apps: Cognitive Services OpenAI User, Storage Blob Data Contributor,
Storage Blob Delegator, and—when `IMAGE_JOB_MODE=azure`—Storage Queue Data
Contributor and Cosmos DB Data Contributor.

## Build and Run

From the repository root:

```bash
docker compose up --build
```

The services are available at:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- OpenAPI schema: http://localhost:8000/api/v1/openapi.json

The frontend calls the backend through its same-origin Next.js proxy. Inside the
Compose network, that proxy uses `http://backend:80`; browser code never needs to
address the Docker service directly.

Stop the stack with:

```bash
docker compose down
```

To force a clean image rebuild without deleting unrelated Docker data:

```bash
docker compose build --no-cache
docker compose up
```

## Build Services Individually

Backend image:

```bash
docker build -t visionary-lab-backend -f backend/Dockerfile .
docker run --rm --env-file .env -p 8000:80 visionary-lab-backend
```

Frontend image:

```bash
docker build -t visionary-lab-frontend frontend
docker run --rm -p 3000:3000 \
  -e BACKEND_API_URL=http://host.docker.internal:8000 \
  -e NEXT_PUBLIC_API_PROTOCOL=http \
  -e NEXT_PUBLIC_API_HOSTNAME=host.docker.internal \
  -e NEXT_PUBLIC_API_PORT=8000 \
  visionary-lab-frontend
```

## Local Networking Limitations

Azure resources provisioned by this repository use private endpoints for Blob,
Queue, and Cosmos DB. A local Docker container cannot reach those endpoints
unless the host is connected to the virtual network. Use one of these options:

- keep `IMAGE_JOB_MODE=memory` and point Blob Storage at a development account
  reachable from the host;
- run `scripts/dev.sh` to use its managed local Azurite container;
- connect the host to the Azure virtual network;
- validate the complete persisted job flow through the deployed application.

GPT-Image-2 generation and editing only require the AI Foundry endpoint and can
be exercised without Queue or Cosmos DB.

## Troubleshooting

Inspect resolved configuration without printing secret values from the running
container:

```bash
docker compose config --quiet
docker compose logs -f backend
docker compose logs -f frontend
```

If authentication fails, verify that all three `AZURE_CLIENT_*` variables are
set and that the service principal has the required data-plane roles. If the
backend health check fails in Azure job mode, verify that both
`AZURE_STORAGE_QUEUE_URL` and `AZURE_COSMOS_DB_ENDPOINT` are set and reachable.
