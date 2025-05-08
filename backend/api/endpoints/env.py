from fastapi import APIRouter
from core.config import settings
from core import dalle_client, llm_client
import os
from typing import Dict, List, Any

router = APIRouter()


@router.get("/env/status", response_model=Dict[str, Any])
def env_status():
    """
    Returns the status of various components in the system, focusing on whether 
    clients are properly initialized rather than specific environment variables.
    This is more reliable across different platforms.
    """
    # Core functionality status
    image_generation_ready = dalle_client is not None
    llm_ready = llm_client is not None

    # Azure storage status
    storage_ready = all([
        settings.AZURE_BLOB_SERVICE_URL,
        settings.AZURE_STORAGE_ACCOUNT_NAME,
        settings.AZURE_STORAGE_ACCOUNT_KEY
    ])

    status = {
        "services": {
            "image_generation": image_generation_ready,
            "llm": llm_ready,
            "storage": storage_ready
        },
        "providers": {
            "using_azure_openai": settings.MODEL_PROVIDER.lower() == "azure",
            "using_direct_openai": settings.MODEL_PROVIDER.lower() == "openai"
        },
        "summary": {
            "all_services_ready": image_generation_ready and llm_ready and storage_ready,
            "image_generation_client": "Initialized" if image_generation_ready else "Not initialized",
            "llm_client": "Initialized" if llm_ready else "Not initialized",
            "storage": "Configured" if storage_ready else "Not configured"
        }
    }

    return status
