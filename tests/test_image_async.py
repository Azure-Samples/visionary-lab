import asyncio
import base64
import io
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.core.exceptions import ResourceExistsError
from fastapi import UploadFile
from pydantic import ValidationError

from backend.core.azure_storage import AzureBlobStorageService
from backend.core.config import settings
from backend.core.gpt_image import (
    GPTImageClient,
    ImageProviderError,
    parse_retry_after_seconds,
)
from backend.core.image_pipeline import ImagePipelineService
from backend.core.sas import get_blob_container_url, get_container_sas_token
from backend.models.images import (
    FLUX_KONTEXT_PRO_MODEL,
    GPT_IMAGE_2_MODEL,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImagePipelineRequest,
    PipelineAction,
    PipelineImageReference,
    ImageSaveRequest,
    TokenUsage,
)


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Y9Z0OkAAAAASUVORK5CYII="
)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Retry-After": "45"}, 45),
        ({"x-ms-retry-after-ms": "2501"}, 3),
    ],
)
def test_parse_retry_after_seconds(headers, expected) -> None:
    assert parse_retry_after_seconds(headers) == expected


def test_parse_retry_after_http_date() -> None:
    now = datetime(2026, 8, 26, 10, 0, tzinfo=timezone.utc)
    retry_at = now + timedelta(seconds=75)

    assert parse_retry_after_seconds(
        {"Retry-After": format_datetime(retry_at, usegmt=True)},
        now=now,
    ) == 75


@pytest.mark.asyncio
async def test_flux_rate_limit_preserves_retry_after_through_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "AI_FOUNDRY_ENDPOINT",
        "https://example.services.ai.azure.com",
    )
    response = MagicMock(status_code=429, is_error=True)
    response.headers = {"Retry-After": "90"}
    response.json.return_value = {"error": {"message": "provider busy"}}
    http_client = MagicMock()
    http_client.post = AsyncMock(return_value=response)

    async def token_provider() -> str:
        return "token"

    client = GPTImageClient(
        provider="azure",
        deployment_name="flux-kontext-deployment",
        model=FLUX_KONTEXT_PRO_MODEL,
        token_provider=token_provider,
        client=http_client,
    )

    with pytest.raises(ImageProviderError) as provider_error:
        await client.generate_image(prompt="A studio portrait")

    http_error = ImagePipelineService._provider_http_exception(provider_error.value)
    assert http_error.status_code == 429
    assert http_error.headers == {"Retry-After": "90"}


@pytest.mark.asyncio
async def test_pipeline_resolves_durable_blob_references_at_execution_time() -> None:
    storage = SimpleNamespace(
        download_asset_async=AsyncMock(return_value=(_ONE_PIXEL_PNG, "image/png"))
    )
    service = ImagePipelineService()
    request = ImagePipelineRequest(
        action=PipelineAction.EDIT,
        prompt="Preserve the subject",
        source_image_blobs=[
            PipelineImageReference(
                blob_name="story/reference.png",
                container="images",
            )
        ],
    )

    resolved = await service._resolve_edit_images(
        request,
        azure_storage_service=storage,
    )

    storage.download_asset_async.assert_awaited_once_with(
        "story/reference.png",
        "images",
    )
    assert resolved == [
        f"data:image/png;base64,{base64.b64encode(_ONE_PIXEL_PNG).decode('ascii')}"
    ]


def test_save_metadata_preserves_provider_token_usage() -> None:
    request = ImageSaveRequest(
        generation_response=ImageGenerationResponse(
            imgen_model_response={"data": [{"b64_json": "encoded"}]},
            token_usage=TokenUsage(
                total_tokens=120,
                input_tokens=20,
                output_tokens=100,
            ),
        ),
        prompt="Campaign frame",
        model="gpt-image-2",
    )

    metadata = ImagePipelineService._build_base_metadata(request)

    assert metadata["token_usage"] == {
        "total_tokens": 120,
        "input_tokens": 20,
        "output_tokens": 100,
        "input_tokens_details": None,
    }


def test_core_import_does_not_initialize_azure_clients() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import backend.core.azure_storage; "
                "from backend.core.resources import _clients; "
                "assert _clients is None"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_gpt_image_client_awaits_sdk_and_closes() -> None:
    sdk_client = MagicMock()
    sdk_client.images.generate = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda **_: {
                "created": 123,
                "data": [{"b64_json": "encoded"}],
            }
        )
    )
    sdk_client.close = AsyncMock()

    client = GPTImageClient(
        provider="openai",
        model=GPT_IMAGE_2_MODEL,
        client=sdk_client,
    )
    async with client:
        result = await client.generate_image(
            prompt="test prompt",
            n=2,
            size="1280x768",
            quality="low",
        )

    sdk_client.images.generate.assert_awaited_once()
    call = sdk_client.images.generate.await_args.kwargs
    assert call["model"] == GPT_IMAGE_2_MODEL
    assert call["size"] == "1280x768"
    assert call["quality"] == "low"
    sdk_client.close.assert_awaited_once()
    assert result["data"] == [{"b64_json": "encoded"}]
    assert result["_model"] == GPT_IMAGE_2_MODEL


@pytest.mark.asyncio
async def test_azure_edit_uses_native_input_fidelity() -> None:
    sdk_client = MagicMock()
    sdk_client.images.edit = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda **_: {"data": [{"b64_json": "edited"}]}
        )
    )
    sdk_client.close = AsyncMock()

    client = GPTImageClient(
        provider="azure",
        deployment_name="image-deployment",
        model=GPT_IMAGE_2_MODEL,
        client=sdk_client,
    )
    result = await client.edit_image(
        prompt="edit it",
        image=("source.png", _ONE_PIXEL_PNG, "image/png"),
        input_fidelity="high",
    )

    call = sdk_client.images.edit.await_args.kwargs
    assert call["model"] == "image-deployment"
    assert call["input_fidelity"] == "high"
    assert "extra_body" not in call
    assert result["data"][0]["b64_json"] == "edited"


@pytest.mark.asyncio
async def test_azure_gpt_image_2_rejects_webp_output() -> None:
    sdk_client = MagicMock()
    sdk_client.images.generate = AsyncMock()
    client = GPTImageClient(
        provider="azure",
        deployment_name="image-deployment",
        model=GPT_IMAGE_2_MODEL,
        client=sdk_client,
    )

    with pytest.raises(ValueError, match="Azure GPT-Image-2 output_format"):
        await client.generate_image(prompt="test", output_format="webp")

    sdk_client.images.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_openai_gpt_image_2_passes_through_webp_output() -> None:
    sdk_client = MagicMock()
    sdk_client.images.generate = AsyncMock(
        return_value=SimpleNamespace(
            model_dump=lambda **_: {"data": [{"b64_json": "encoded"}]}
        )
    )
    client = GPTImageClient(
        provider="openai",
        model=GPT_IMAGE_2_MODEL,
        client=sdk_client,
    )

    await client.generate_image(
        prompt="test",
        quality="auto",
        output_format="webp",
        background="transparent",
    )

    call = sdk_client.images.generate.await_args.kwargs
    assert call["output_format"] == "webp"
    assert call["quality"] == "auto"
    assert call["background"] == "transparent"


def test_gpt_image_client_uses_explicit_gpt_image_2_deployment(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "IMAGEGEN_2_DEPLOYMENT",
        "gpt-image-2-deployment",
    )

    client = GPTImageClient(
        provider="azure",
        model=GPT_IMAGE_2_MODEL,
        client=MagicMock(),
    )

    assert client.deployment_name == "gpt-image-2-deployment"


def test_azure_kontext_client_binds_the_configured_deployment(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "AI_FOUNDRY_ENDPOINT",
        "https://example.cognitiveservices.azure.com",
    )
    monkeypatch.setattr(
        settings,
        "FLUX_KONTEXT_DEPLOYMENT",
        "flux-kontext-deployment",
    )

    async def token_provider() -> str:
        return "token"

    with (
        patch("backend.core.gpt_image.AsyncAzureOpenAI") as sdk_client_class,
        patch("backend.core.gpt_image.httpx.AsyncClient") as http_client_class,
    ):
        client = GPTImageClient(
            provider="azure",
            model=FLUX_KONTEXT_PRO_MODEL,
            credential=MagicMock(),
            token_provider=token_provider,
        )

    sdk_client_class.assert_not_called()
    http_client_class.assert_called_once()
    assert client.deployment_name == "flux-kontext-deployment"


@pytest.mark.asyncio
async def test_azure_kontext_generation_uses_provider_api(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "AI_FOUNDRY_ENDPOINT",
        "https://example.cognitiveservices.azure.com",
    )
    response = MagicMock(status_code=200, is_error=False)
    response.json.return_value = {
        "created": 123,
        "data": [{"url": "https://example.test/flux.png"}],
    }
    http_client = MagicMock()
    http_client.post = AsyncMock(return_value=response)
    http_client.close = None
    http_client.aclose = AsyncMock()

    async def token_provider() -> str:
        return "token"

    client = GPTImageClient(
        provider="azure",
        deployment_name="flux-kontext-deployment",
        model=FLUX_KONTEXT_PRO_MODEL,
        token_provider=token_provider,
        client=http_client,
    )
    result = await client.generate_image(
        prompt="A studio portrait",
        size="1536x1024",
    )

    http_client.post.assert_awaited_once_with(
        "https://example.services.ai.azure.com/providers/blackforestlabs/v1/flux-kontext-pro",
        params={"api-version": "preview"},
        headers={
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
        },
        json={
            "model": "flux-kontext-deployment",
            "prompt": "A studio portrait",
            "aspect_ratio": "3:2",
            "output_format": "png",
        },
    )
    assert result["data"] == [{"url": "https://example.test/flux.png"}]
    assert result["_deployment_name"] == "flux-kontext-deployment"
    assert result["_model"] == FLUX_KONTEXT_PRO_MODEL

    await client.close()
    http_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_azure_kontext_edit_uses_single_base64_reference(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "AI_FOUNDRY_ENDPOINT",
        "https://example.services.ai.azure.com",
    )
    response = MagicMock(status_code=200, is_error=False)
    response.json.return_value = {
        "data": [{"url": "https://example.test/edited.png"}]
    }
    http_client = MagicMock()
    http_client.post = AsyncMock(return_value=response)

    async def token_provider() -> str:
        return "token"

    client = GPTImageClient(
        provider="azure",
        deployment_name="flux-kontext-deployment",
        model=FLUX_KONTEXT_PRO_MODEL,
        token_provider=token_provider,
        client=http_client,
    )
    result = await client.edit_image(
        prompt="Keep the subject and change the background",
        image=("source.png", _ONE_PIXEL_PNG, "image/png"),
        size="1024x1536",
        output_format="png",
    )

    call = http_client.post.await_args.kwargs
    assert call["json"] == {
        "model": "flux-kontext-deployment",
        "prompt": "Keep the subject and change the background",
        "input_image": base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
        "aspect_ratio": "2:3",
        "output_format": "png",
    }
    assert result["data"] == [{"url": "https://example.test/edited.png"}]


@pytest.mark.asyncio
async def test_sync_azure_token_provider_is_kept_off_event_loop() -> None:
    main_thread = threading.get_ident()
    provider_threads: list[int] = []

    def sync_token_provider() -> str:
        provider_threads.append(threading.get_ident())
        return "token"

    provider = GPTImageClient._ensure_async_token_provider(sync_token_provider)

    assert await provider() == "token"
    assert provider_threads and provider_threads[0] != main_thread


@pytest.mark.parametrize(
    "size",
    ["auto", "1024x1024", "1280x768", "3840x2160"],
)
def test_gpt_image_2_accepts_documented_sizes(size: str) -> None:
    request = ImageGenerationRequest(prompt="test", size=size)

    assert request.model == GPT_IMAGE_2_MODEL
    assert request.size == size
    assert request.quality == "high"


@pytest.mark.parametrize(
    ("size", "message"),
    [
        ("1025x1024", "multiples of 16"),
        ("3072x768", "aspect ratio"),
        ("800x800", "total pixels"),
        ("3840x2176", "total pixels"),
        ("3856x2160", "long edge"),
        ("1024-by-1024", "WIDTHxHEIGHT"),
    ],
)
def test_gpt_image_2_rejects_invalid_sizes(size: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ImageGenerationRequest(prompt="test", size=size)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("quality", "ultra", "quality"),
        ("output_format", "gif", "output_format"),
        ("response_format", "url", "response_format"),
        ("background", "solid", "background"),
    ],
)
def test_gpt_image_2_rejects_unsupported_options(
    field: str,
    value: str,
    message: str,
) -> None:
    kwargs = {field: value}
    with pytest.raises(ValidationError, match=message):
        ImageGenerationRequest(prompt="test", **kwargs)


def test_gpt_image_2_preserves_cross_provider_options() -> None:
    request = ImageGenerationRequest(
        prompt="test",
        quality="auto",
        output_format="webp",
        background="opaque",
    )

    assert request.quality == "auto"
    assert request.output_format == "webp"
    assert request.background == "opaque"


def test_gpt_image_2_rejects_transparent_jpeg() -> None:
    with pytest.raises(ValidationError, match="transparent backgrounds"):
        ImageGenerationRequest(
            prompt="test",
            output_format="jpeg",
            background="transparent",
        )


@pytest.mark.parametrize(
    "legacy_model",
    ["gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"],
)
def test_legacy_openai_image_models_are_rejected(legacy_model: str) -> None:
    with pytest.raises(ValidationError, match="Model must be one of"):
        ImageGenerationRequest(prompt="test", model=legacy_model)


def test_flux_remains_a_supported_alternative() -> None:
    request = ImageGenerationRequest(
        prompt="test",
        model="flux-kontext-pro",
        size="1024x1024",
        quality="auto",
        output_format="webp",
        response_format="url",
        background="opaque",
    )

    assert request.model == "flux-kontext-pro"


def test_flux_rejects_multiple_outputs_per_request() -> None:
    with pytest.raises(ValidationError, match="one image per request"):
        ImageGenerationRequest(
            prompt="test",
            model=FLUX_KONTEXT_PRO_MODEL,
            n=2,
        )


@pytest.mark.asyncio
async def test_process_pipeline_reports_generation_progress() -> None:
    service = ImagePipelineService()
    service.generate = AsyncMock(
        return_value=ImageGenerationResponse(
            success=True,
            imgen_model_response={"data": [{"b64_json": "encoded"}]},
        )
    )
    progress: list[tuple[str, dict[str, object]]] = []

    async def report(stage: str, details: dict[str, object]) -> None:
        progress.append((stage, details))

    response = await service.process_pipeline(
        ImagePipelineRequest(prompt="test", n=1),
        progress_callback=report,
    )

    assert response.success is True
    assert progress == [
        ("generating", {"status": "started", "total": 1, "completed": 0}),
        ("generating", {"status": "completed", "completed": 1, "total": 1}),
    ]


@pytest.mark.asyncio
async def test_save_is_bounded_concurrent_and_job_names_are_idempotent() -> None:
    active = 0
    max_active = 0
    filenames: list[str] = []
    overwrite_flags: list[bool] = []

    class Storage:
        async def upload_asset(
            self,
            file: UploadFile,
            metadata=None,
            folder_path=None,
            *,
            overwrite_existing: bool = False,
        ):
            nonlocal active, max_active
            filenames.append(file.filename)
            overwrite_flags.append(overwrite_existing)
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return {
                "blob_name": f"{folder_path or ''}{file.filename}",
                "container": "images",
                "url": f"https://storage/{file.filename}",
                "original_filename": file.filename,
            }

    encoded = base64.b64encode(_ONE_PIXEL_PNG).decode("ascii")
    generation = ImageGenerationResponse(
        success=True,
        imgen_model_response={
            "data": [{"b64_json": encoded} for _ in range(3)],
        },
    )
    request = ImageSaveRequest(
        generation_response=generation,
        prompt="test",
        folder_path="jobs/",
        metadata={"image_job_id": "job-123"},
    )
    progress: list[tuple[str, dict[str, object]]] = []

    async def report(stage: str, details: dict[str, object]) -> None:
        progress.append((stage, details))

    result = await ImagePipelineService(max_concurrent_io=2).save(
        request,
        azure_storage_service=Storage(),
        progress_callback=report,
    )

    assert max_active == 2
    assert result.total_saved == 3
    expected_filenames = [
        "image_job_job-123_1.png",
        "image_job_job-123_2.png",
        "image_job_job-123_3.png",
    ]
    assert sorted(filenames) == expected_filenames
    assert [image.original_filename for image in result.saved_images] == (
        expected_filenames
    )
    assert overwrite_flags == [True, True, True]
    assert progress[0] == (
        "saving",
        {"status": "started", "total": 3, "completed": 0},
    )
    assert progress[-1][1]["status"] == "completed"


@pytest.mark.asyncio
async def test_blob_upload_uses_native_async_sdk() -> None:
    blob_client = MagicMock()
    blob_client.url = "https://storage/image.png"
    blob_client.exists = AsyncMock()
    blob_client.upload_blob = AsyncMock()
    container_client = MagicMock()
    container_client.get_blob_client.return_value = blob_client
    async_blob_service_client = MagicMock()
    async_blob_service_client.get_container_client.return_value = container_client
    async_blob_service_client.close = AsyncMock()
    async_credential = MagicMock()
    async_credential.close = AsyncMock()
    sync_blob_service_client = MagicMock()
    sync_credential = MagicMock()

    service = object.__new__(AzureBlobStorageService)
    service.image_container = "images"
    service._async_blob_service_client = async_blob_service_client
    service._async_credential = async_credential
    service.blob_service_client = sync_blob_service_client
    service._sync_credential = sync_credential
    service._async_ready = True
    service._closed = False

    upload = UploadFile(filename="image.png", file=io.BytesIO(_ONE_PIXEL_PNG))
    result = await service.upload_asset(
        upload,
        overwrite_existing=True,
    )

    assert result["blob_name"] == "image.png"
    blob_client.exists.assert_not_awaited()
    blob_client.upload_blob.assert_awaited_once()

    await service.close()
    async_blob_service_client.close.assert_awaited_once()
    async_credential.close.assert_awaited_once()
    sync_blob_service_client.close.assert_called_once()
    sync_credential.close.assert_called_once()


@pytest.mark.asyncio
async def test_blob_storage_uses_azurite_connection_string_and_creates_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "AZURE_STORAGE_CONNECTION_STRING",
        "UseDevelopmentStorage=true",
    )
    monkeypatch.setattr(settings, "AZURE_BLOB_SERVICE_URL", None)
    monkeypatch.setattr(settings, "AZURE_STORAGE_ACCOUNT_NAME", None)

    sync_client = MagicMock()
    sync_client.url = "http://127.0.0.1:10000/devstoreaccount1/"
    async_client = MagicMock()
    async_client.close = AsyncMock()
    container_client = MagicMock()
    container_client.create_container = AsyncMock()
    async_client.get_container_client.return_value = container_client

    with (
        patch(
            "backend.core.azure_storage.BlobServiceClient.from_connection_string",
            return_value=sync_client,
        ) as sync_from_connection_string,
        patch(
            "backend.core.azure_storage.AsyncBlobServiceClient.from_connection_string",
            return_value=async_client,
        ) as async_from_connection_string,
        patch("backend.core.azure_storage.DefaultAzureCredential") as sync_credential,
        patch(
            "backend.core.azure_storage.AsyncDefaultAzureCredential"
        ) as async_credential,
    ):
        service = AzureBlobStorageService()
        await service._ensure_async_storage_ready()
        await service._ensure_async_storage_ready()
        await service.close()

    resolved = sync_from_connection_string.call_args.args[0]
    assert "AccountName=devstoreaccount1" in resolved
    assert "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1" in resolved
    async_from_connection_string.assert_called_once_with(resolved)
    container_client.create_container.assert_awaited_once_with(public_access="blob")
    sync_credential.assert_not_called()
    async_credential.assert_not_called()
    sync_client.close.assert_called_once()
    async_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_blob_storage_accepts_existing_azurite_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "AZURE_STORAGE_CONNECTION_STRING",
        "UseDevelopmentStorage=true",
    )

    sync_client = MagicMock()
    sync_client.url = "http://127.0.0.1:10000/devstoreaccount1/"
    async_client = MagicMock()
    container_client = MagicMock()
    container_client.create_container = AsyncMock(
        side_effect=ResourceExistsError("container already exists")
    )
    container_client.set_container_access_policy = AsyncMock()
    async_client.get_container_client.return_value = container_client

    with (
        patch(
            "backend.core.azure_storage.BlobServiceClient.from_connection_string",
            return_value=sync_client,
        ),
        patch(
            "backend.core.azure_storage.AsyncBlobServiceClient.from_connection_string",
            return_value=async_client,
        ),
    ):
        service = AzureBlobStorageService()
        await service._ensure_async_storage_ready()

    assert service._async_ready is True
    container_client.set_container_access_policy.assert_awaited_once_with(
        signed_identifiers={},
        public_access="blob",
    )


def test_blob_storage_preserves_managed_identity_without_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AZURE_STORAGE_CONNECTION_STRING", None)
    monkeypatch.setattr(
        settings,
        "AZURE_BLOB_SERVICE_URL",
        "https://managed.blob.core.windows.net/",
    )

    credential = MagicMock()
    sync_client = MagicMock()
    with (
        patch(
            "backend.core.azure_storage.DefaultAzureCredential",
            return_value=credential,
        ) as credential_factory,
        patch(
            "backend.core.azure_storage.BlobServiceClient",
            return_value=sync_client,
        ) as client_factory,
    ):
        service = AzureBlobStorageService()

    credential_factory.assert_called_once_with()
    client_factory.assert_called_once_with(
        account_url="https://managed.blob.core.windows.net/",
        credential=credential,
    )
    assert service._is_local_emulator is False


@pytest.mark.asyncio
async def test_azurite_browser_access_needs_no_sas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "AZURE_STORAGE_CONNECTION_STRING",
        "UseDevelopmentStorage=true",
    )
    monkeypatch.setattr(settings, "AZURE_BLOB_SERVICE_URL", None)
    monkeypatch.setattr(settings, "AZURE_STORAGE_ACCOUNT_NAME", None)

    token, _ = await get_container_sas_token("images")

    assert token == ""
    assert get_blob_container_url("images") == (
        "http://127.0.0.1:10000/devstoreaccount1/images"
    )


@pytest.mark.asyncio
async def test_save_waits_for_all_outputs_and_returns_partial_success() -> None:
    completed: list[str] = []

    class PartialStorage:
        async def upload_asset(
            self,
            file: UploadFile,
            metadata=None,
            folder_path=None,
            *,
            overwrite_existing: bool = False,
        ):
            if file.filename and file.filename.endswith("_2.png"):
                raise RuntimeError("second upload failed")
            await asyncio.sleep(0.02)
            completed.append(file.filename or "")
            return {
                "blob_name": file.filename,
                "container": "images",
                "url": f"https://storage/{file.filename}",
                "original_filename": file.filename,
            }

    encoded = base64.b64encode(_ONE_PIXEL_PNG).decode("ascii")
    generation = ImageGenerationResponse(
        success=True,
        imgen_model_response={
            "data": [{"b64_json": encoded} for _ in range(3)],
        },
    )
    progress: list[tuple[str, dict[str, object]]] = []

    async def report(stage: str, details: dict[str, object]) -> None:
        progress.append((stage, details))

    result = await ImagePipelineService(max_concurrent_io=3).save(
        ImageSaveRequest(
            generation_response=generation,
            prompt="partial",
            metadata={"image_job_id": "partial-job"},
        ),
        azure_storage_service=PartialStorage(),
        progress_callback=report,
    )

    assert result.total_saved == 2
    assert len(completed) == 2
    assert {image.original_index for image in result.saved_images} == {1, 3}
    assert progress[-1][1]["failed"] == 1
    assert any(item[1].get("error") == "second upload failed" for item in progress)


@pytest.mark.asyncio
async def test_save_awaits_native_async_cosmos_metadata() -> None:
    class Storage:
        async def upload_asset(self, file: UploadFile, **kwargs):
            return {
                "blob_name": file.filename,
                "container": "images",
                "url": f"https://storage/{file.filename}",
                "original_filename": file.filename,
                "size": 1,
            }

        async def delete_asset_async(self, blob_name: str, container_name: str):
            raise AssertionError("metadata write should not require compensation")

    cosmos = MagicMock()
    cosmos.upsert_asset_metadata = AsyncMock(return_value={})
    encoded = base64.b64encode(_ONE_PIXEL_PNG).decode("ascii")
    generation = ImageGenerationResponse(
        success=True,
        imgen_model_response={"data": [{"b64_json": encoded}]},
    )

    result = await ImagePipelineService().save(
        ImageSaveRequest(
            generation_response=generation,
            prompt="async metadata",
            metadata={"image_job_id": "async-metadata"},
        ),
        azure_storage_service=Storage(),
        cosmos_service=cosmos,
    )

    assert result.total_saved == 1
    cosmos.upsert_asset_metadata.assert_awaited_once()
