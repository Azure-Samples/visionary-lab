"""On-demand, renewable Blob SAS tokens with no import-time Azure calls."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContainerSasPermissions, generate_container_sas
from azure.storage.blob.aio import BlobServiceClient

from .config import settings

_sas_cache: dict[str, tuple[str, datetime]] = {}
_sas_lock = asyncio.Lock()


async def get_container_sas_token(
    container_name: str,
    *,
    lifetime: timedelta = timedelta(hours=1),
) -> tuple[str, datetime]:
    """Mint and cache a user-delegation read SAS token."""
    now = datetime.now(timezone.utc)
    cached = _sas_cache.get(container_name)
    if cached and cached[1] > now + timedelta(minutes=5):
        return cached

    async with _sas_lock:
        now = datetime.now(timezone.utc)
        cached = _sas_cache.get(container_name)
        if cached and cached[1] > now + timedelta(minutes=5):
            return cached

        account_url = settings.AZURE_BLOB_SERVICE_URL
        if not account_url and settings.AZURE_STORAGE_ACCOUNT_NAME:
            account_url = (
                f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/"
            )
        if not account_url or not settings.AZURE_STORAGE_ACCOUNT_NAME:
            raise RuntimeError("Azure Blob Storage is not configured")

        credential = DefaultAzureCredential()
        service_client = BlobServiceClient(
            account_url=account_url,
            credential=credential,
        )
        start_time = now - timedelta(minutes=5)
        expiry_time = now + lifetime
        try:
            delegation_key = await service_client.get_user_delegation_key(
                key_start_time=start_time,
                key_expiry_time=expiry_time,
            )
            token = generate_container_sas(
                account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
                container_name=container_name,
                user_delegation_key=delegation_key,
                permission=ContainerSasPermissions(read=True, list=True),
                expiry=expiry_time,
                start=start_time,
            )
        finally:
            await service_client.close()
            await credential.close()

        result = (token, expiry_time)
        _sas_cache[container_name] = result
        return result
