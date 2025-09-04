from pydantic_settings import BaseSettings
from typing import List, Optional
from pydantic import Extra


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Visionary Lab API"

    # Model Provider Configuration
    MODEL_PROVIDER: str = "azure"  # Can be 'azure' or 'openai'

    # Azure OpenAI for Sora Video Generation
    SORA_AOAI_RESOURCE: Optional[str] = None  # The Azure OpenAI resource name for Sora
    SORA_DEPLOYMENT: Optional[str] = None  # The Sora deployment name
    SORA_AOAI_API_KEY: Optional[str] = None  # The Azure OpenAI API key for Sora

    # Azure OpenAI for LLM
    # The Azure OpenAI resource name for LLM
    LLM_AOAI_RESOURCE: Optional[str] = None
    LLM_DEPLOYMENT: Optional[str] = None  # The LLM deployment name
    LLM_AOAI_API_KEY: Optional[str] = None  # The Azure OpenAI API key for LLM

    # Azure OpenAI for Image Generation
    # The Azure OpenAI resource name for image generation
    IMAGEGEN_AOAI_RESOURCE: Optional[str] = None
    # The image generation deployment name
    IMAGEGEN_DEPLOYMENT: Optional[str] = None
    # The Azure OpenAI API key for image generation
    IMAGEGEN_AOAI_API_KEY: Optional[str] = None

    # OpenAI API for Image Generation with GPT-Image-1
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None  # Organization ID for OpenAI
    # Whether organization is verified on OpenAI
    OPENAI_ORG_VERIFIED: bool = False
    GPT_IMAGE_MAX_TOKENS: int = 150000  # Maximum token usage limit

    # Azure Blob Storage Settings
    # Option 1: Connection string (deprecated)
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = None

    # Option 2: Individual credential components (preferred)
    # https://<account>.blob.core.windows.net/
    AZURE_BLOB_SERVICE_URL: Optional[str] = None
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = None  # Storage account name
    AZURE_STORAGE_ACCOUNT_KEY: Optional[str] = None  # Storage account key

    # Container names
    AZURE_BLOB_IMAGE_CONTAINER: str = "images"  # Container name for images
    AZURE_BLOB_VIDEO_CONTAINER: str = "videos"  # Container name for videos

    # Azure Cosmos DB Settings
    AZURE_COSMOS_DB_ENDPOINT: Optional[str] = None  # Cosmos DB endpoint URL
    AZURE_COSMOS_DB_KEY: Optional[str] = None  # Cosmos DB primary key
    AZURE_COSMOS_DB_ID: str = "visionarylab"  # Database name
    AZURE_COSMOS_CONTAINER_ID: str = "metadata"  # Container name for metadata

    # Alternative: Managed Identity settings (for Azure-hosted deployments)
    USE_MANAGED_IDENTITY: bool = (
        False  # Set to True when running on Azure with Managed Identity
    )

    # Azure OpenAI API Version
    # API version for Azure OpenAI services
    AOAI_API_VERSION: str = "2025-04-01-preview"

    # File storage paths
    UPLOAD_DIR: str = "./static/uploads"
    IMAGE_DIR: str = "./static/images"
    VIDEO_DIR: str = "./static/videos"

    # GPT-Image-1 Default Settings
    GPT_IMAGE_DEFAULT_SIZE: str = "1024x1024"
    GPT_IMAGE_DEFAULT_QUALITY: str = "high"
    GPT_IMAGE_DEFAULT_FORMAT: str = "PNG"
    GPT_IMAGE_ALLOW_TRANSPARENT: bool = True
    # Max file size in MB for image uploads
    GPT_IMAGE_MAX_FILE_SIZE_MB: int = 25

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = Extra.allow


settings = Settings()
