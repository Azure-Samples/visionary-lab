"""Integration test fixtures — uses real Azure credentials from .env."""

import os
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val or val.startswith("your-"):
        pytest.skip(f"{key} not configured in .env")
    return val


@pytest.fixture(scope="session")
def azure_settings():
    """Validate that all required env vars are set, skip otherwise."""
    return {
        "AI_FOUNDRY_ENDPOINT": _require_env("AI_FOUNDRY_ENDPOINT"),
        "LLM_DEPLOYMENT": _require_env("LLM_DEPLOYMENT"),
        "IMAGEGEN_DEPLOYMENT": _require_env("IMAGEGEN_DEPLOYMENT"),
        "AZURE_STORAGE_ACCOUNT_NAME": _require_env("AZURE_STORAGE_ACCOUNT_NAME"),
    }


@pytest.fixture(scope="session")
def image_client(azure_settings):
    """Real GPTImageClient using Azure credentials."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backend.core.gpt_image import GPTImageClient
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    return GPTImageClient(credential=credential, token_provider=token_provider, provider="azure")


@pytest.fixture(scope="session")
def llm_client(azure_settings):
    """Real Azure OpenAI LLM client."""
    from openai import AzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backend.core.config import settings
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )


@pytest.fixture(scope="session")
def async_llm_client(azure_settings):
    """Real async Azure OpenAI LLM client."""
    from openai import AsyncAzureOpenAI
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from backend.core.config import settings
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    return AsyncAzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
