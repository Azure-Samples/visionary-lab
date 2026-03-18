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
        "IMAGEGEN_AOAI_RESOURCE": _require_env("IMAGEGEN_AOAI_RESOURCE"),
        "IMAGEGEN_DEPLOYMENT": _require_env("IMAGEGEN_DEPLOYMENT"),
        "IMAGEGEN_AOAI_API_KEY": _require_env("IMAGEGEN_AOAI_API_KEY"),
        "LLM_AOAI_RESOURCE": _require_env("LLM_AOAI_RESOURCE"),
        "LLM_DEPLOYMENT": _require_env("LLM_DEPLOYMENT"),
        "LLM_AOAI_API_KEY": _require_env("LLM_AOAI_API_KEY"),
        "SORA_AOAI_RESOURCE": _require_env("SORA_AOAI_RESOURCE"),
        "SORA_DEPLOYMENT": _require_env("SORA_DEPLOYMENT"),
        "SORA_AOAI_API_KEY": _require_env("SORA_AOAI_API_KEY"),
        "AZURE_STORAGE_ACCOUNT_NAME": _require_env("AZURE_STORAGE_ACCOUNT_NAME"),
        "AZURE_STORAGE_ACCOUNT_KEY": _require_env("AZURE_STORAGE_ACCOUNT_KEY"),
    }


@pytest.fixture(scope="session")
def image_client(azure_settings):
    """Real GPTImageClient using Azure credentials."""
    from backend.core.gpt_image import GPTImageClient
    return GPTImageClient(provider="azure")


@pytest.fixture
def sora_client(azure_settings):
    """Real Sora client — fresh per test to avoid event loop issues."""
    from backend.core.sora import Sora
    from backend.core.config import settings
    return Sora(
        resource_name=settings.SORA_AOAI_RESOURCE,
        deployment_name=settings.SORA_DEPLOYMENT,
        api_key=settings.SORA_AOAI_API_KEY,
    )


@pytest.fixture(scope="session")
def llm_client(azure_settings):
    """Real Azure OpenAI LLM client."""
    from openai import AzureOpenAI
    from backend.core.config import settings
    return AzureOpenAI(
        azure_endpoint=f"https://{settings.LLM_AOAI_RESOURCE}.openai.azure.com/",
        api_key=settings.LLM_AOAI_API_KEY,
        api_version="2025-01-01-preview",
    )


@pytest.fixture(scope="session")
def async_llm_client(azure_settings):
    """Real async Azure OpenAI LLM client."""
    from openai import AsyncAzureOpenAI
    from backend.core.config import settings
    return AsyncAzureOpenAI(
        azure_endpoint=f"https://{settings.LLM_AOAI_RESOURCE}.openai.azure.com/",
        api_key=settings.LLM_AOAI_API_KEY,
        api_version="2025-01-01-preview",
    )
