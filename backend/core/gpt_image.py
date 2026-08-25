from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Optional

from openai import AsyncAzureOpenAI, AsyncOpenAI

from backend.core.config import settings
from backend.models.images import (
    FLUX_KONTEXT_PRO_MODEL,
    GPT_IMAGE_2_MODEL,
    validate_image_model,
    validate_image_options,
    validate_image_size,
)

logger = logging.getLogger(__name__)

_AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


class GPTImageClient:
    """Native async client for GPT image generation and editing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        organization_id: Optional[str] = None,
        provider: Optional[str] = None,
        deployment_name: Optional[str] = None,
        model: Optional[str] = None,
        credential: Any = None,
        token_provider: Any = None,
        client: Any = None,
    ) -> None:
        self.provider = (provider or settings.MODEL_PROVIDER).lower()
        self.model = model or settings.DEFAULT_IMAGE_MODEL
        validate_image_model(self.model)
        self.deployment_name = (
            deployment_name or self._get_deployment_for_model(self.model)
            if self.provider == "azure"
            else None
        )
        self.credential = credential
        self.token_provider = token_provider
        self._owns_credential = False
        self._closed = False

        if client is not None:
            self.client = client
            return

        if self.provider == "azure":
            if self.credential is None:
                from azure.identity.aio import (
                    DefaultAzureCredential,
                    get_bearer_token_provider,
                )

                self.credential = DefaultAzureCredential()
                self.token_provider = get_bearer_token_provider(
                    self.credential, _AZURE_OPENAI_SCOPE
                )
                self._owns_credential = True
            elif self.token_provider is None:
                self.token_provider = self._token_provider_for(self.credential)
            else:
                self.token_provider = self._ensure_async_token_provider(
                    self.token_provider
                )

            self.endpoint = (
                settings.AI_FOUNDRY_ENDPOINT.rstrip("/")
                if settings.AI_FOUNDRY_ENDPOINT
                else ""
            )
            self.client = AsyncAzureOpenAI(
                azure_ad_token_provider=self.token_provider,
                azure_endpoint=self.endpoint,
                api_version=settings.AOAI_API_VERSION,
            )
            logger.info(
                "Initialized async Azure GPT Image client (model: %s, deployment: %s)",
                self.model,
                self.deployment_name,
            )
            return

        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("API key must be provided for OpenAI")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            organization=organization_id or settings.OPENAI_ORG_ID,
        )
        logger.info("Initialized async OpenAI GPT Image client (model: %s)", self.model)

    @staticmethod
    def _token_provider_for(credential: Any):
        """Adapt either an async or sync Azure credential for AsyncAzureOpenAI."""
        get_token = credential.get_token
        if inspect.iscoroutinefunction(get_token):

            async def async_token_provider() -> str:
                token = await get_token(_AZURE_OPENAI_SCOPE)
                return token.token

            return async_token_provider

        async def sync_token_provider() -> str:
            # Compatibility for callers that inject a synchronous Azure credential.
            token = await asyncio.to_thread(get_token, _AZURE_OPENAI_SCOPE)
            return token.token

        return sync_token_provider

    @staticmethod
    def _ensure_async_token_provider(token_provider: Any):
        """Keep legacy sync token providers off the application event loop."""
        if inspect.iscoroutinefunction(token_provider):
            return token_provider

        async def async_token_provider() -> str:
            token = await asyncio.to_thread(token_provider)
            if inspect.isawaitable(token):
                token = await token
            return token

        return async_token_provider

    def _get_deployment_for_model(self, model: str) -> Optional[str]:
        mapping = {
            GPT_IMAGE_2_MODEL: settings.IMAGEGEN_2_DEPLOYMENT,
            FLUX_KONTEXT_PRO_MODEL: settings.FLUX_KONTEXT_DEPLOYMENT,
        }
        deployment = mapping.get(model)
        if not deployment:
            logger.warning(
                "No Azure deployment configured for model %s",
                model,
            )
        return deployment

    async def generate_image(
        self,
        prompt: str,
        model: Optional[str] = None,
        n: int = 1,
        size: str = "auto",
        response_format: str = "b64_json",
        quality: str = "high",
        background: str = "auto",
        output_format: str = "png",
        output_compression: int = 100,
        moderation: str = "auto",
        user: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate images without blocking the event loop."""
        requested_model = model or self.model
        validate_image_model(requested_model)
        validate_image_size(requested_model, size)
        validate_image_options(
            requested_model,
            quality=quality,
            output_format=output_format,
            response_format=response_format,
            background=background,
        )
        self._validate_provider_options(
            requested_model,
            output_format=output_format,
        )
        provider_model = (
            self.deployment_name if self.provider == "azure" else requested_model
        )
        if not provider_model:
            raise ValueError("An image model deployment must be configured")

        params: dict[str, Any] = {
            "prompt": prompt,
            "model": provider_model,
            "n": n,
            "size": size,
        }
        if user:
            params["user"] = user

        is_flux = "flux" in requested_model.lower()
        if not is_flux:
            params["quality"] = quality
            if background != "auto":
                params["background"] = background
            if output_format != "png":
                params["output_format"] = output_format
            if output_format in {"webp", "jpeg"} and output_compression != 100:
                params["output_compression"] = output_compression
            if moderation != "auto":
                params["moderation"] = moderation
        elif output_format != "png":
            params["output_format"] = output_format

        # GPT image models always return base64. Preserve response_format in the
        # public signature for compatibility without sending an unsupported field.
        _ = response_format

        logger.info(
            "Generating %s image(s) with provider %s, model %s, quality %s, size %s",
            n,
            self.provider,
            provider_model,
            quality,
            size,
        )
        response = await self.client.images.generate(**params)
        return self._format_response(response)

    async def edit_image(self, **kwargs: Any) -> dict[str, Any]:
        """Edit one or more images through the async OpenAI SDK."""
        params = {key: value for key, value in kwargs.items() if value is not None}
        requested_model = str(params.get("model") or self.model)
        validate_image_model(requested_model)
        validate_image_size(requested_model, str(params.get("size") or "auto"))
        response_format = str(params.pop("response_format", "b64_json"))
        output_format = str(params.get("output_format") or "png")
        validate_image_options(
            requested_model,
            quality=str(params.get("quality") or "high"),
            output_format=output_format,
            response_format=response_format,
            background=str(params.get("background") or "auto"),
        )
        self._validate_provider_options(
            requested_model,
            output_format=output_format,
        )
        provider_model = (
            self.deployment_name if self.provider == "azure" else requested_model
        )
        if not provider_model:
            raise ValueError("An image model deployment must be configured")
        params["model"] = provider_model

        image_count = (
            len(params["image"]) if isinstance(params.get("image"), list) else 1
        )
        logger.info(
            "Editing with provider %s, model %s, %s reference image(s), quality %s, size %s",
            self.provider,
            provider_model,
            image_count,
            params.get("quality", "auto"),
            params.get("size", "auto"),
        )
        response = await self.client.images.edit(**params)
        return self._format_response(response)

    def _validate_provider_options(
        self,
        model: str,
        *,
        output_format: str,
    ) -> None:
        """Apply provider-specific restrictions after shared model validation."""
        if (
            self.provider == "azure"
            and model == GPT_IMAGE_2_MODEL
            and output_format == "webp"
        ):
            raise ValueError(
                "Azure GPT-Image-2 output_format must be png or jpeg"
            )

    def _format_response(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            result = dict(response)
        elif hasattr(response, "model_dump"):
            result = response.model_dump(exclude_none=True)
        else:
            result = {
                "created": getattr(response, "created", None),
                "data": [
                    self._dump_response_item(item)
                    for item in (getattr(response, "data", None) or [])
                ],
            }
            usage = getattr(response, "usage", None)
            if usage is not None:
                result["usage"] = self._dump_response_item(usage)

        result.setdefault("data", [])
        result["_deployment_name"] = self.deployment_name
        result["_model"] = self.model
        return result

    @staticmethod
    def _dump_response_item(value: Any) -> Any:
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)
        return {
            key: item
            for key in (
                "url",
                "b64_json",
                "revised_prompt",
                "total_tokens",
                "input_tokens",
                "output_tokens",
                "input_tokens_details",
            )
            if (item := getattr(value, key, None)) is not None
        }

    async def close(self) -> None:
        """Release HTTP and credential resources owned by this client."""
        if self._closed:
            return
        self._closed = True

        close_client = getattr(self.client, "close", None)
        if close_client is not None:
            result = close_client()
            if inspect.isawaitable(result):
                await result

        if self._owns_credential and self.credential is not None:
            close_credential = getattr(self.credential, "close", None)
            if close_credential is not None:
                result = close_credential()
                if inspect.isawaitable(result):
                    await result

    async def __aenter__(self) -> "GPTImageClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        await self.close()
