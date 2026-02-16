"""Shared test fixtures for the Visionary Lab backend.

All tests run without real Azure credentials by mocking external services.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set environment variables BEFORE importing anything from the backend,
# so that Settings() picks up test values instead of requiring real creds.
os.environ.setdefault("MODEL_PROVIDER", "azure")
os.environ.setdefault("IMAGEGEN_AOAI_RESOURCE", "test-resource")
os.environ.setdefault("IMAGEGEN_DEPLOYMENT", "test-deployment")
os.environ.setdefault("IMAGEGEN_AOAI_API_KEY", "test-key")
os.environ.setdefault("LLM_AOAI_RESOURCE", "test-llm-resource")
os.environ.setdefault("LLM_DEPLOYMENT", "test-llm-deployment")
os.environ.setdefault("LLM_AOAI_API_KEY", "test-llm-key")
os.environ.setdefault("SORA_AOAI_RESOURCE", "test-sora-resource")
os.environ.setdefault("SORA_DEPLOYMENT", "test-sora-deployment")
os.environ.setdefault("SORA_AOAI_API_KEY", "test-sora-key")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_NAME", "teststorage")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT_KEY", "dGVzdC1rZXk=")
os.environ.setdefault("AZURE_BLOB_SERVICE_URL", "https://teststorage.blob.core.windows.net/")
os.environ.setdefault("AZURE_BLOB_IMAGE_CONTAINER", "images")
os.environ.setdefault("AZURE_BLOB_VIDEO_CONTAINER", "videos")
os.environ.setdefault("AZURE_COSMOS_DB_ENDPOINT", "https://test.documents.azure.com:443/")
os.environ.setdefault("AZURE_COSMOS_DB_KEY", "test-cosmos-key")
os.environ.setdefault("USE_MANAGED_IDENTITY", "false")

from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def mock_azure_storage():
    """Mock Azure Blob Storage so no real connection is made."""
    mock_service = MagicMock()
    mock_container = MagicMock()
    mock_service.get_container_client.return_value = mock_container
    mock_container.exists.return_value = True

    with patch(
        "backend.core.azure_storage.BlobServiceClient",
        return_value=mock_service,
    ):
        yield mock_service


@pytest.fixture(scope="session")
def mock_cosmos():
    """Mock Cosmos DB client."""
    with patch("backend.core.cosmos_client.CosmosClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_db = MagicMock()
        mock_client.get_database_client.return_value = mock_db
        mock_container = MagicMock()
        mock_db.get_container_client.return_value = mock_container
        yield mock_container


@pytest.fixture(scope="session")
def app(mock_azure_storage, mock_cosmos):
    """Create a FastAPI test application with mocked external services."""
    from backend.main import app as _app
    return _app


@pytest.fixture(scope="session")
def client(app):
    """HTTP test client for the FastAPI application."""
    return TestClient(app)
