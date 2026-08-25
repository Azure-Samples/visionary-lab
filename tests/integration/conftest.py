"""Integration test fixtures — uses real Azure credentials from .env."""

import os
import pytest
import pytest_asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    test_sentinels = {
        "https://test-foundry.cognitiveservices.azure.com/",
        "test-llm-deployment",
        "test-gpt-image-2-deployment",
        "teststorage",
    }
    if (
        not val
        or val.startswith("your-")
        or "<name_of_" in val
        or val in test_sentinels
    ):
        pytest.skip(f"{key} not configured in .env")
    return val


@pytest.fixture(scope="session")
def image_settings():
    """Validate the settings required for live GPT-Image-2 tests."""
    return {
        "AI_FOUNDRY_ENDPOINT": _require_env("AI_FOUNDRY_ENDPOINT"),
        "IMAGEGEN_2_DEPLOYMENT": _require_env("IMAGEGEN_2_DEPLOYMENT"),
    }


@pytest.fixture(scope="session")
def llm_settings():
    """Validate the settings required for live LLM analysis tests."""
    return {
        "AI_FOUNDRY_ENDPOINT": _require_env("AI_FOUNDRY_ENDPOINT"),
        "LLM_DEPLOYMENT": _require_env("LLM_DEPLOYMENT"),
    }


@pytest.fixture(scope="session")
def storage_settings():
    """Validate the settings required only by live Blob Storage tests."""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    if connection_string:
        return {
            "AZURE_STORAGE_CONNECTION_STRING": connection_string,
            "is_emulator": connection_string.lower() == "usedevelopmentstorage=true",
        }
    return {
        "AZURE_STORAGE_ACCOUNT_NAME": _require_env("AZURE_STORAGE_ACCOUNT_NAME"),
        "AZURE_BLOB_SERVICE_URL": _require_env("AZURE_BLOB_SERVICE_URL"),
        "is_emulator": False,
    }


@pytest_asyncio.fixture
async def image_client(image_settings):
    """Real GPTImageClient using Azure credentials."""
    from backend.core.gpt_image import GPTImageClient

    client = GPTImageClient(provider="azure")
    yield client
    await client.close()


@pytest.fixture
def llm_client(llm_settings):
    """Real Azure OpenAI LLM client."""
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backend.core.config import settings
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    client = AzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
    try:
        yield client
    finally:
        client.close()
        credential.close()


@pytest_asyncio.fixture
async def async_llm_client(llm_settings):
    """Real async Azure OpenAI LLM client."""
    from openai import AsyncAzureOpenAI
    from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
    from backend.core.config import settings

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
    try:
        yield client
    finally:
        await client.close()
        await credential.close()
