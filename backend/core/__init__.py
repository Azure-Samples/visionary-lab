import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.storage.blob import BlobServiceClient, generate_container_sas, ContainerSasPermissions
from openai import AzureOpenAI, AsyncAzureOpenAI

from .config import settings
from .gpt_image import GPTImageClient

logger = logging.getLogger(__name__)

# Shared credential for all Azure services
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

# Initialize GPT-Image client (using default model)
try:
    image_client = GPTImageClient(
        credential=credential,
        token_provider=token_provider,
        model=settings.DEFAULT_IMAGE_MODEL,
    )
    logger.info(f"Initialized GPT-Image client with managed identity (model: {settings.DEFAULT_IMAGE_MODEL})")
except Exception as e:
    logger.error(f"Failed to initialize GPT-Image client: {str(e)}")
    image_client = None

# Initialize LLM client (sync)
try:
    llm_client = AzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
    logger.info("Initialized LLM client with managed identity")
except Exception as e:
    logger.error(f"Failed to initialize LLM client: {str(e)}")
    llm_client = None

# Initialize async LLM client
try:
    async_llm_client = AsyncAzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
    logger.info("Initialized async LLM client with managed identity")
except Exception as e:
    logger.error(f"Failed to initialize async LLM client: {str(e)}")
    async_llm_client = None


def _get_blob_service_client() -> BlobServiceClient:
    """Get a BlobServiceClient using managed identity."""
    account_url = settings.AZURE_BLOB_SERVICE_URL
    if not account_url and settings.AZURE_STORAGE_ACCOUNT_NAME:
        account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/"
    return BlobServiceClient(account_url=account_url, credential=credential)


def _generate_sas(container_name: str) -> str | None:
    """Generate a 4-hour read/list SAS token using User Delegation Key."""
    try:
        blob_client = _get_blob_service_client()
        start_time = datetime.now(timezone.utc)
        expiry_time = start_time + timedelta(hours=4)

        user_delegation_key = blob_client.get_user_delegation_key(
            key_start_time=start_time,
            key_expiry_time=expiry_time,
        )

        token = generate_container_sas(
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=container_name,
            user_delegation_key=user_delegation_key,
            permission=ContainerSasPermissions(read=True, list=True),
            expiry=expiry_time,
            start=start_time,
        )
        logger.info(f"Generated User Delegation SAS token for {container_name} container.")
        return token
    except Exception as e:
        logger.error(f"Failed to generate SAS token for {container_name}: {e}")
        return None


@lru_cache(maxsize=1)
def get_image_sas_token() -> str | None:
    """Generate the image-container SAS token on first use, not at import time."""
    return _generate_sas(settings.AZURE_BLOB_IMAGE_CONTAINER)
