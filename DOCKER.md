# Docker Setup for AI Content Lab

This document provides instructions for building and running both the frontend and backend applications using Docker.

## Prerequisites

- Docker and Docker Compose installed on your system
- Git to clone the repository

## Project Structure

This project has a specific structure where:
- The pyproject.toml file with dependencies is in the root folder
- The backend code is in the `backend` folder
- The frontend code is in the `frontend` folder

The Docker setup is configured to accommodate this structure.

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Azure AI Foundry
AI_FOUNDRY_ENDPOINT=https://your-foundry-name.cognitiveservices.azure.com/
LLM_DEPLOYMENT=gpt-4o
IMAGEGEN_DEPLOYMENT=gpt-image-1-5

# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account-name
AZURE_STORAGE_ACCOUNT_KEY=your-storage-account-key
AZURE_BLOB_SERVICE_URL=https://your-storage-account-name.blob.core.windows.net/
```

## Building and Running the Applications

### Using Docker Compose (Recommended)

From the root directory, run:

```bash
docker-compose up -d
```

This will build and start both the frontend and backend containers. The applications will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (mapped to internal port 80)
- API Documentation: http://localhost:8000/docs

To stop the containers:

```bash
docker-compose down
```

### Completely Rebuilding (If Issues Occur)

If you encounter PATH issues or other problems, completely rebuild from scratch with:

```bash
# Remove containers, networks, and images
docker-compose down --rmi all
docker system prune -f

# Rebuild and start with no cache
docker-compose build --no-cache
docker-compose up -d
```

### Building and Running Individually

#### Backend

To build and run the backend individually, you need to build from the root directory:

```bash
docker build -t ai-content-lab-backend -f backend/Dockerfile .
docker run -p 8000:80 \
  -e PYTHONPATH=/app \
  -e PATH=/app/.venv/bin:${PATH} \
  -e AI_FOUNDRY_ENDPOINT=https://your-foundry-name.cognitiveservices.azure.com/ \
  -e LLM_DEPLOYMENT=gpt-4o \
  -e IMAGEGEN_DEPLOYMENT=gpt-image-1-5 \
  -e AZURE_STORAGE_ACCOUNT_NAME=your-storage-account-name \
  -e AZURE_STORAGE_ACCOUNT_KEY=your-storage-account-key \
  ai-content-lab-backend
```

#### Frontend

```bash
cd frontend
docker build -t ai-content-lab-frontend .
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_PROTOCOL=http \
  -e NEXT_PUBLIC_API_HOSTNAME=localhost \
  -e NEXT_PUBLIC_API_PORT=80 \
  -e NEXT_PUBLIC_STORAGE_ACCOUNT_NAME=your-storage-account-name \
  ai-content-lab-frontend
```

## Multi-Service Deployment

The docker-compose.yml file is configured to build and run both services from the root directory by:

1. **Setting the build context for backend to the root folder**: This allows access to the pyproject.toml file
2. **Using the correct path to the Dockerfile**: `dockerfile: backend/Dockerfile`
3. **Setting volume mounts appropriately**: Static files are mapped to the correct path in the container
4. **Environment variables**: PYTHONPATH and PATH are set to ensure proper module imports and command execution
5. **Service networking**: The frontend references the backend by service name

## Development vs. Production

The Dockerfiles are configured for production use. For development:

1. Backend: For development with hot reload, modify the CMD in the Dockerfile to:
   ```
   CMD ["exec /app/.venv/bin/fastapi run backend/main.py --port 80 --host 0.0.0.0 --reload"]
   ```

2. Frontend: Change the CMD in the Dockerfile to `["npm", "run", "dev"]`

## Backend Dockerfile Notes

The backend Dockerfile:
- Uses the official uv package manager approach as recommended in the [uv documentation](https://docs.astral.sh/uv/guides/integration/fastapi/#deployment)
- Creates a virtual environment with `uv venv .venv`
- Installs the fastapi-cli package in the virtual environment
- Adds the virtual environment bin directory to PATH
- Uses a shell wrapper to execute the fastapi command to avoid PATH issues
- Sets environment variables to ensure imports and commands work correctly
- Exposes port 80 internally, mapped to port 8000 externally

## Persistent Storage

The Docker Compose setup includes a volume mount for the backend's static directory to persist generated content between container restarts:

```yaml
volumes:
  - ./backend/static:/app/backend/static
```

## Accessing Logs

To view logs for a specific service:

```bash
docker-compose logs backend
docker-compose logs frontend
```

Add the `-f` flag to follow the logs in real-time.

## Troubleshooting

### Backend Container Fails to Start

If the backend container fails to start, check:
1. Environment variables are correctly set
2. The AI Foundry endpoint and model deployment names are valid
3. Logs with `docker-compose logs backend`
4. Make sure the PYTHONPATH and PATH environment variables are set correctly
5. Try rebuilding from scratch as mentioned in the "Completely Rebuilding" section
6. Check if the fastapi command exists in the virtual environment with `docker exec -it <container_id> /bin/sh -c "ls -la /app/.venv/bin/"`

### Frontend Cannot Connect to Backend

By default, the frontend is configured to connect to the backend using the service name `backend` and port 80. If running the containers separately, modify the frontend environment variables to use the correct hostname and port.
