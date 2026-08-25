from unittest.mock import AsyncMock

import pytest

from backend.api.endpoints.gallery import (
    _get_gallery_items_from_blob_storage,
    create_folder,
    list_folders,
)


class LocalBlobStorage:
    def normalize_folder_path(self, folder_path=None):
        if not folder_path:
            return ""
        return folder_path.strip("/") + "/"

    def list_blobs(self, container_name, prefix=None, limit=100, marker=None):
        return {
            "container": container_name,
            "continuation_token": None,
            "blobs": [
                {
                    "name": "campaign/.folder",
                    "size": 0,
                    "content_type": None,
                    "creation_time": "2026-08-25T00:00:00+00:00",
                    "last_modified": "2026-08-25T00:00:00+00:00",
                    "url": "http://localhost/campaign/.folder",
                    "metadata": {},
                    "folder_path": "campaign/",
                },
                {
                    "name": "campaign/result.png",
                    "size": 123,
                    "content_type": "image/png",
                    "creation_time": "2026-08-25T00:01:00+00:00",
                    "last_modified": "2026-08-25T00:01:00+00:00",
                    "url": "http://localhost/campaign/result.png",
                    "metadata": {},
                    "folder_path": "campaign/",
                },
            ],
        }

    def list_folders(self, container_name):
        return ["campaign/"]


@pytest.mark.asyncio
async def test_local_gallery_falls_back_to_blob_listing():
    response = await _get_gallery_items_from_blob_storage(
        limit=50,
        offset=0,
        folder_path="campaign",
        tags=None,
        azure_storage_service=LocalBlobStorage(),
    )

    assert response.total == 1
    assert response.items[0].name == "campaign/result.png"
    assert response.items[0].folder_path == "campaign/"


@pytest.mark.asyncio
async def test_local_folder_list_and_create_use_blob_markers():
    marker = AsyncMock()
    blob_service = type(
        "BlobService",
        (),
        {"get_blob_client": lambda self, **kwargs: marker},
    )()
    storage = LocalBlobStorage()
    storage._ensure_async_storage_ready = AsyncMock()
    storage._get_async_blob_service_client = lambda: blob_service

    folders = await list_folders(
        media_type=None,
        cosmos_service=None,
        azure_storage_service=storage,
    )
    created = await create_folder(
        folder_path="new-folder",
        media_type=None,
        cosmos_service=None,
        azure_storage_service=storage,
    )

    assert folders["folders"] == ["campaign/"]
    assert folders["source"] == "blob_storage"
    assert created["folder_path"] == "new-folder"
    marker.upload_blob.assert_awaited_once_with(b"", overwrite=True)
