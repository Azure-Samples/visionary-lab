from typing import Dict, List

from fastapi import APIRouter

from backend.core.config import settings

router = APIRouter()


def _is_setting_defined(setting_name: str) -> bool:
    value = getattr(settings, setting_name, None)
    return value is not None and value != ""


@router.get("/env/status", response_model=Dict[str, List[str]])
def env_status():
    """
    Returns which environment variables are set and which are missing based on the Settings class.
    """
    # Required variables (must be set for the application to work properly)
    required_vars = [
        'SORA_AOAI_RESOURCE',
        'SORA_AOAI_API_KEY',
        'SORA_DEPLOYMENT',
        'LLM_AOAI_RESOURCE',
        'LLM_DEPLOYMENT',
        'LLM_AOAI_API_KEY',
        'IMAGEGEN_AOAI_RESOURCE',
        'IMAGEGEN_DEPLOYMENT',
        'IMAGEGEN_AOAI_API_KEY',
        'AZURE_BLOB_SERVICE_URL',
        'AZURE_STORAGE_ACCOUNT_NAME',
        'AZURE_STORAGE_ACCOUNT_KEY',
        'AZURE_BLOB_IMAGE_CONTAINER',
        'AZURE_BLOB_VIDEO_CONTAINER',
    ]

    # Optional variables (app can function without them)
    optional_vars = []

    set_required_vars = [var for var in required_vars if _is_setting_defined(var)]
    missing_vars = [var for var in required_vars if var not in set_required_vars]
    set_optional_vars = [var for var in optional_vars if _is_setting_defined(var)]
    set_vars = [*set_required_vars, *set_optional_vars]

    return {
        "set": set_vars,
        "missing": missing_vars,
        "optional_missing": [var for var in optional_vars if var not in set_optional_vars],
    }
