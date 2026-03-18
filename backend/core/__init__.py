import logging
from openai import AzureOpenAI, AsyncAzureOpenAI
from .config import settings
from .sora import Sora
from .gpt_image import GPTImageClient
from datetime import datetime, timedelta, timezone
from azure.storage.blob import generate_container_sas, ContainerSasPermissions

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Sora 2 client
try:
    sora_client = Sora(
        resource_name=settings.SORA_AOAI_RESOURCE,
        deployment_name=settings.SORA_DEPLOYMENT,
        api_key=settings.SORA_AOAI_API_KEY
    )
    logger.info(
        f"Initialized Sora 2 client with resource: {settings.SORA_AOAI_RESOURCE}, "
        f"deployment: {settings.SORA_DEPLOYMENT}")
except Exception as e:
    logger.error(f"Failed to initialize Sora 2 client: {str(e)}")
    sora_client = None

# Initialize GPT-Image client (using default model)
try:
    # Using OpenAI API directly for GPT-Image
    image_client = GPTImageClient(
        api_key=settings.OPENAI_API_KEY,
        organization_id=settings.OPENAI_ORG_ID if settings.OPENAI_ORG_ID else None,
        model=settings.DEFAULT_IMAGE_MODEL
    )
    logger.info(f"Initialized GPT-Image client using OpenAI API with default model: {settings.DEFAULT_IMAGE_MODEL}")
except Exception as e:
    logger.error(f"Failed to initialize GPT-Image client: {str(e)}")
    image_client = None

# Initialize LLM client (sync)
try:
    llm_client = AzureOpenAI(
        azure_endpoint=f"https://{settings.LLM_AOAI_RESOURCE}.openai.azure.com/",
        api_key=settings.LLM_AOAI_API_KEY,
        # TODO: make configurable. Video generation uses 2025-02-15-preview (does not work with LLM)
        api_version="2025-01-01-preview"
    )
    logger.info(
        f"Initialized LLM client with resource: {settings.LLM_AOAI_RESOURCE}")
except Exception as e:
    logger.error(f"Failed to initialize LLM client: {str(e)}")
    llm_client = None

# Initialize async LLM client (for non-blocking operations)
try:
    async_llm_client = AsyncAzureOpenAI(
        azure_endpoint=f"https://{settings.LLM_AOAI_RESOURCE}.openai.azure.com/",
        api_key=settings.LLM_AOAI_API_KEY,
        api_version="2025-01-01-preview"
    )
    logger.info(
        f"Initialized async LLM client with resource: {settings.LLM_AOAI_RESOURCE}")
except Exception as e:
    logger.error(f"Failed to initialize async LLM client: {str(e)}")
    async_llm_client = None

def _generate_sas(container_name: str) -> str | None:
    """Generate a 4-hour read/list SAS token for a blob container."""
    try:
        token = generate_container_sas(
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=container_name,
            account_key=settings.AZURE_STORAGE_ACCOUNT_KEY,
            permission=ContainerSasPermissions(read=True, list=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=4),
        )
        logger.info(f"Generated SAS token for {container_name} container.")
        return token
    except Exception as e:
        logger.error(f"Failed to generate SAS token for {container_name}: {e}")
        return None

video_sas_token = _generate_sas(settings.AZURE_BLOB_VIDEO_CONTAINER)
image_sas_token = _generate_sas(settings.AZURE_BLOB_IMAGE_CONTAINER)
