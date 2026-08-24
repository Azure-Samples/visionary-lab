"""Lazy process-owned AI clients with explicit shutdown."""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from dataclasses import dataclass
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.identity.aio import (
    DefaultAzureCredential as AsyncDefaultAzureCredential,
    get_bearer_token_provider as get_async_bearer_token_provider,
)
from openai import AsyncAzureOpenAI, AzureOpenAI

from .config import settings

logger = logging.getLogger(__name__)
_AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass(slots=True)
class CoreClients:
    credential: Any
    async_credential: Any
    image_client: Any
    llm_client: Any
    async_llm_client: Any


_clients: CoreClients | None = None
_clients_lock = threading.Lock()


def _create_clients() -> CoreClients:
    from .gpt_image import GPTImageClient

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, _AZURE_OPENAI_SCOPE)
    async_credential = AsyncDefaultAzureCredential()
    async_token_provider = get_async_bearer_token_provider(
        async_credential, _AZURE_OPENAI_SCOPE
    )

    image_client = GPTImageClient(
        credential=credential,
        token_provider=token_provider,
        model=settings.DEFAULT_IMAGE_MODEL,
    )
    llm_client = AzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2025-01-01-preview",
    )
    async_llm_client = AsyncAzureOpenAI(
        azure_endpoint=settings.AI_FOUNDRY_ENDPOINT,
        azure_ad_token_provider=async_token_provider,
        api_version="2025-01-01-preview",
    )
    logger.info("Initialized process-owned Azure AI clients")
    return CoreClients(
        credential=credential,
        async_credential=async_credential,
        image_client=image_client,
        llm_client=llm_client,
        async_llm_client=async_llm_client,
    )


def get_core_clients() -> CoreClients:
    global _clients
    if _clients is not None:
        return _clients
    with _clients_lock:
        if _clients is None:
            _clients = _create_clients()
        return _clients


async def close_core_clients() -> None:
    global _clients
    with _clients_lock:
        clients, _clients = _clients, None
    if clients is None:
        return

    for resource in (
        clients.image_client,
        clients.async_llm_client,
        clients.async_credential,
    ):
        close = getattr(resource, "close", None)
        if close is None:
            continue
        result = close()
        if inspect.isawaitable(result):
            await result

    for resource in (clients.llm_client, clients.credential):
        close = getattr(resource, "close", None)
        if close is not None:
            close()


async def warm_core_clients() -> None:
    """Warm lazy clients without blocking the event loop on construction."""
    await asyncio.to_thread(get_core_clients)
