import asyncio
import base64
import io
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from backend.core.azure_storage import AzureBlobStorageService
from backend.core.gpt_image import GPTImageClient
from backend.core.image_pipeline import ImagePipelineService
from backend.models.images import (
    ImageEditRequest,
    ImageGenerationResponse,
    ImagePipelineRequest,
    ImageSaveRequest,
)


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Y9Z0OkAAAAASUVORK5CYII="
)


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
        model="gpt-image-1.5",
        client=sdk_client,
    )
    async with client:
        result = await client.generate_image(prompt="test prompt", n=2)

    sdk_client.images.generate.assert_awaited_once()
    sdk_client.close.assert_awaited_once()
    assert result["data"] == [{"b64_json": "encoded"}]
    assert result["_model"] == "gpt-image-1.5"


@pytest.mark.asyncio
async def test_azure_edit_uses_async_sdk_and_preview_extra_body() -> None:
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
        model="gpt-image-1.5",
        client=sdk_client,
    )
    result = await client.edit_image(
        prompt="edit it",
        image=("source.png", _ONE_PIXEL_PNG, "image/png"),
        input_fidelity="high",
    )

    call = sdk_client.images.edit.await_args.kwargs
    assert call["model"] == "image-deployment"
    assert call["extra_body"] == {"input_fidelity": "high"}
    assert result["data"][0]["b64_json"] == "edited"


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


@pytest.mark.asyncio
async def test_pipeline_preserves_http_exception_status() -> None:
    service = ImagePipelineService()
    request = ImageEditRequest(
        prompt="edit",
        model="gpt-image-1-mini",
        image=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.edit(request)

    assert exc_info.value.status_code == 400


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
