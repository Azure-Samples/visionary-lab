from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import Extra, Field, validator


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Visionary Lab API"

    # Model Provider Configuration
    MODEL_PROVIDER: str = "azure"  # Can be 'azure' or 'openai'

    # AI Foundry endpoint (unified for all AI services via managed identity)
    AI_FOUNDRY_ENDPOINT: Optional[str] = None

    # Model deployment names
    LLM_DEPLOYMENT: Optional[str] = None
    IMAGEGEN_DEPLOYMENT: Optional[str] = None
    IMAGEGEN_15_DEPLOYMENT: Optional[str] = None
    IMAGEGEN_1_MINI_DEPLOYMENT: Optional[str] = None
    FLUX_KONTEXT_DEPLOYMENT: Optional[str] = None
    DEFAULT_IMAGE_MODEL: str = "gpt-image-1.5"

    # OpenAI API for direct OpenAI usage (non-Azure)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    OPENAI_ORG_VERIFIED: bool = False
    GPT_IMAGE_MAX_TOKENS: int = 150000

    # Azure Blob Storage Settings (managed identity — no keys)
    AZURE_BLOB_SERVICE_URL: Optional[str] = None
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = None
    CDN_BLOB_URL: Optional[str] = None

    # Container names
    AZURE_BLOB_IMAGE_CONTAINER: str = "images"

    # Durable image-generation jobs (managed identity — no queue keys)
    AZURE_STORAGE_QUEUE_URL: Optional[str] = None
    AZURE_STORAGE_QUEUE_NAME: str = "image-generation-jobs"
    AZURE_STORAGE_POISON_QUEUE_NAME: str = "image-generation-jobs-poison"
    IMAGE_JOB_MODE: str = "auto"  # auto, azure, or memory
    IMAGE_JOB_ROLE: str = "all"  # api, worker, or all (local development)
    IMAGE_JOB_CONCURRENCY: int = 2
    IMAGE_JOB_POLL_INTERVAL_SECONDS: float = 1.0
    IMAGE_JOB_CANCELLATION_POLL_SECONDS: float = 2.0
    IMAGE_JOB_VISIBILITY_TIMEOUT_SECONDS: int = 600
    IMAGE_JOB_HEARTBEAT_INTERVAL_SECONDS: float = 0.0  # 0 = visibility / 3
    IMAGE_JOB_RECONCILE_INTERVAL_SECONDS: float = 5.0
    IMAGE_JOB_MAX_ATTEMPTS: int = 3
    IMAGE_JOB_RETENTION_SECONDS: int = 60 * 60 * 24 * 30

    # CORS Configuration
    CORS_ALLOWED_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins, or * for all origins"
    )

    # Azure Cosmos DB Settings (managed identity — no keys)
    AZURE_COSMOS_DB_ENDPOINT: Optional[str] = None
    AZURE_COSMOS_DB_ID: str = "visionarylab"
    AZURE_COSMOS_CONTAINER_ID: str = "metadata"

    # Azure OpenAI API Version
    AOAI_API_VERSION: str = "2025-04-01-preview"

    # File storage paths
    UPLOAD_DIR: str = "./static/uploads"
    IMAGE_DIR: str = "./static/images"

    # Logging Configuration
    LOG_LEVEL: str = "INFO"


    # GPT-Image-1 Default Settings
    GPT_IMAGE_DEFAULT_SIZE: str = "1024x1024"
    GPT_IMAGE_DEFAULT_QUALITY: str = "high"
    GPT_IMAGE_DEFAULT_FORMAT: str = "PNG"
    GPT_IMAGE_ALLOW_TRANSPARENT: bool = True
    GPT_IMAGE_MAX_FILE_SIZE_MB: int = 25

    @validator('CORS_ALLOWED_ORIGINS')
    def validate_cors_origins(cls, v):
        """Validate CORS origins configuration to prevent Azure InvalidXmlNodeValue errors"""
        if v == "*":
            return v
        
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        
        if "*" in origins and len(origins) > 1:
            raise ValueError(
                "Cannot mix wildcard '*' with specific origins in CORS configuration. "
                "Use either '*' alone for all origins, or specify individual origins without '*'."
            )
        
        for origin in origins:
            if origin != "*" and not (origin.startswith("http://") or origin.startswith("https://")):
                raise ValueError(f"Invalid origin format: {origin}. Origins must start with http:// or https://")
        
        return v

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = Extra.allow


settings = Settings()
