import asyncio
import inspect
import os
import uuid
import logging
from typing import Dict, Optional, List, Tuple
from fastapi import UploadFile
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.blob.aio import BlobServiceClient as AsyncBlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

from backend.core.config import settings

logger = logging.getLogger(__name__)


class AzureBlobStorageService:
    """Service for handling image assets in Azure Blob Storage."""

    def __init__(self):
        """Initialize Azure Blob Storage client"""
        self.image_container = settings.AZURE_BLOB_IMAGE_CONTAINER

        self._account_url = settings.AZURE_BLOB_SERVICE_URL
        if not self._account_url and settings.AZURE_STORAGE_ACCOUNT_NAME:
            self._account_url = (
                f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/"
            )

        self._sync_credential = DefaultAzureCredential()
        self.blob_service_client = BlobServiceClient(
            account_url=self._account_url,
            credential=self._sync_credential,
        )
        self._async_credential = None
        self._async_blob_service_client = None
        self._async_setup_lock = asyncio.Lock()
        self._async_ready = False
        self._closed = False

        # Container/CORS setup used to perform synchronous network calls here.
        # The upload path now initializes those resources through the aio SDK,
        # keeping construction safe when it happens on the application event loop.

    def _get_async_blob_service_client(self) -> AsyncBlobServiceClient:
        """Lazily create the native async client used by upload operations."""
        client = getattr(self, "_async_blob_service_client", None)
        if client is None:
            credential = AsyncDefaultAzureCredential()
            client = AsyncBlobServiceClient(
                account_url=self._account_url,
                credential=credential,
            )
            self._async_credential = credential
            self._async_blob_service_client = client
        return client

    async def _ensure_async_storage_ready(self) -> None:
        """Finish lazy async-client setup; infrastructure owns containers/CORS."""
        if getattr(self, "_async_ready", False):
            return

        setup_lock = getattr(self, "_async_setup_lock", None)
        if setup_lock is None:
            setup_lock = asyncio.Lock()
            self._async_setup_lock = setup_lock

        async with setup_lock:
            if self._async_ready:
                return
            self._get_async_blob_service_client()
            self._async_ready = True

    async def close(self) -> None:
        """Release async and legacy sync Azure client resources."""
        if getattr(self, "_closed", False):
            return
        self._closed = True

        for resource_name in (
            "_async_blob_service_client",
            "_async_credential",
        ):
            resource = getattr(self, resource_name, None)
            close = getattr(resource, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result

        for resource_name in ("blob_service_client", "_sync_credential"):
            resource = getattr(self, resource_name, None)
            close = getattr(resource, "close", None)
            if close is not None:
                close()

    async def __aenter__(self) -> "AzureBlobStorageService":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    def list_blobs(self, container_name: str, prefix: Optional[str] = None,
                   limit: int = 100, marker: Optional[str] = None) -> Dict:
        """
        List blobs in a container with pagination support

        Args:
            container_name: Name of the container to list blobs from
            prefix: Optional prefix filter for blob names (like a folder path)
            limit: Maximum number of blobs to return (default 100, max 5000)
            marker: Optional marker for resuming from a specific point
            delimiter: Optional delimiter for hierarchy (e.g. '/' for folder-like structure)

        Returns:
            Dictionary with blobs and continuation token
        """
        try:
            # Get container client
            container_client = self.blob_service_client.get_container_client(
                container_name)

            # Ensure limit is reasonable
            if limit > 5000:
                limit = 5000

            # Get blob list
            blob_list = []

            # Prepare parameters for list_blobs
            list_params = {
                "name_starts_with": prefix,
                "results_per_page": limit,
                "include": ['metadata']
            }

            blob_items = container_client.list_blobs(
                **list_params).by_page(marker)

            # Get the first page of results
            blobs_page = next(blob_items)

            # Process the results
            for blob in blobs_page:
                # Convert creation time to ISO format if it exists
                creation_time = blob.creation_time.isoformat() if blob.creation_time else None
                last_modified = blob.last_modified.isoformat() if blob.last_modified else None

                # Get blob URL
                blob_client = container_client.get_blob_client(blob.name)
                url = blob_client.url

                # Get blob properties with metadata (list_blobs sometimes doesn't include it properly)
                properties = blob_client.get_blob_properties()
                metadata = properties.metadata or {}

                # Extract folder path from blob name
                folder_path = ""
                if "/" in blob.name:
                    folder_path = blob.name.rsplit("/", 1)[0] + "/"

                blob_list.append({
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_settings.content_type if blob.content_settings else None,
                    "creation_time": creation_time,
                    "last_modified": last_modified,
                    "url": url,
                    "metadata": metadata,
                    "folder_path": folder_path
                })

            # Get the continuation token for the next page
            continuation_token = blob_items.continuation_token

            return {
                "blobs": blob_list,
                "continuation_token": continuation_token,
                "container": container_name,
            }

        except ResourceNotFoundError:
            return {
                "blobs": [],
                "continuation_token": None,
                "container": container_name,
            }

    def _ensure_container_exists(self, container_name: str) -> None:
        """
        Ensure the specified container exists, creating it if necessary

        Args:
            container_name: Name of the container to check/create
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name)
            container_client.get_container_properties()
        except ResourceNotFoundError:
            self.blob_service_client.create_container(container_name)

    def normalize_folder_path(self, folder_path: Optional[str] = None) -> str:
        """
        Normalize a folder path to ensure consistent format

        Args:
            folder_path: Optional folder path to normalize

        Returns:
            Normalized folder path or empty string if None
        """
        if not folder_path:
            return ""

        # Trim whitespace
        folder_path = folder_path.strip()

        # Remove leading slash if present
        if folder_path.startswith("/"):
            folder_path = folder_path[1:]

        # Ensure path ends with slash if not empty
        if folder_path and not folder_path.endswith("/"):
            folder_path = f"{folder_path}/"

        return folder_path

    @staticmethod
    def _preprocess_metadata_value(value: str) -> str:
        """Sanitize a metadata value to ASCII-only for Azure blob headers."""
        if value is None:
            return ""
        import re
        str_value = re.sub(r'\s+', ' ', str(value).replace('\n', ' ').replace('\r', ' ').replace('\t', ' '))
        sanitized = ''.join(
            c if 32 <= ord(c) <= 126 and c not in '<>{}[]?#%' else '_'
            for c in str_value
        ).strip()
        return sanitized or "_"

    async def upload_asset(
        self,
        file: UploadFile,
        metadata: Optional[Dict[str, str]] = None,
        folder_path: Optional[str] = None,
        *,
        overwrite_existing: bool = False,
    ) -> Dict[str, str]:
        """
        Upload an image to Azure Blob Storage.

        Note: Metadata is no longer stored in blob storage - use Cosmos DB instead

        Args:
            file: The uploaded file
            metadata: Optional metadata (ignored - kept for API compatibility)
            folder_path: Optional folder path to store the asset in

        Returns:
            Dictionary with asset information
        """
        try:
            container_name = self.image_container

            # Get file extension and determine content type
            _, ext = os.path.splitext(file.filename)
            content_type = self._get_content_type(ext)

            # Normalize folder path
            normalized_folder_path = self.normalize_folder_path(folder_path)

            await self._ensure_async_storage_ready()
            container_client = self._get_async_blob_service_client().get_container_client(
                container_name
            )

            # Use the provided filename if available, otherwise generate UUID
            if file.filename and file.filename.strip():
                # Remove the extension from the filename to avoid double extensions
                filename_without_ext = os.path.splitext(file.filename)[0]
                # Create blob name with the provided filename
                blob_name = f"{normalized_folder_path}{filename_without_ext}{ext}"
                file_id = filename_without_ext  # For backward compatibility in response
                # Check if blob already exists and handle conflicts
                blob_client = container_client.get_blob_client(blob_name)

                # Job retries intentionally overwrite deterministic names. Other
                # uploads retain the historical collision-avoidance behavior.
                if not overwrite_existing and await blob_client.exists():
                    # Use first 8 chars of UUID
                    unique_suffix = str(uuid.uuid4())[:8]
                    blob_name = f"{normalized_folder_path}{filename_without_ext}_{unique_suffix}{ext}"
                    file_id = f"{filename_without_ext}_{unique_suffix}"
            else:
                # Fallback to UUID if no filename provided
                file_id = str(uuid.uuid4())
                blob_name = f"{normalized_folder_path}{file_id}{ext}"

            blob_client = container_client.get_blob_client(blob_name)

            # Set content settings
            content_settings = ContentSettings(content_type=content_type)

            # Upload the file (no metadata stored in blob storage)
            file_content = await file.read()

            # Get image dimensions for return data (but don't store in blob metadata)
            width, height = None, None
            try:
                width, height = await asyncio.to_thread(
                    self._get_image_dimensions, file_content
                )
            except Exception as e:
                # If we can't get dimensions, log but continue
                logger.warning(f"Could not get image dimensions: {str(e)}")

            await blob_client.upload_blob(
                data=file_content,
                content_settings=content_settings,
                overwrite=True,
            )

            # Get the blob URL
            blob_url = blob_client.url

            # Prepare return data with extracted technical metadata
            return_data = {
                "file_id": file_id,
                "blob_name": blob_name,
                "container": container_name,
                "url": blob_url,
                "size": len(file_content),
                "content_type": content_type,
                "original_filename": file.filename,
                "folder_path": normalized_folder_path
            }

            # Add dimensions if we extracted them
            if width is not None and height is not None:
                return_data["width"] = width
                return_data["height"] = height

            return return_data
        except Exception:
            raise

    async def delete_asset_async(self, blob_name: str, container_name: str) -> bool:
        """Delete a blob through the shared async client."""
        await self._ensure_async_storage_ready()
        blob_client = self._get_async_blob_service_client().get_blob_client(
            container=container_name,
            blob=blob_name,
        )
        try:
            await blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return False

    async def download_asset_async(
        self, blob_name: str, container_name: str
    ) -> tuple[bytes, str | None]:
        """Download a blob with managed identity through the shared aio client."""
        await self._ensure_async_storage_ready()
        blob_client = self._get_async_blob_service_client().get_blob_client(
            container=container_name,
            blob=blob_name,
        )
        properties = await blob_client.get_blob_properties()
        stream = await blob_client.download_blob()
        return await stream.readall(), properties.content_settings.content_type

    @staticmethod
    def _get_image_dimensions(file_content: bytes) -> Tuple[int, int]:
        import io
        from PIL import Image

        with Image.open(io.BytesIO(file_content)) as img:
            return img.width, img.height

    def _get_content_type(self, extension: str) -> str:
        """
        Determine content type based on file extension

        Args:
            extension: File extension including the dot
        Returns:
            MIME type string
        """
        extension = extension.lower()

        # Image content types
        image_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".bmp": "image/bmp"
        }

        return image_types.get(extension, "application/octet-stream")

    def delete_asset(self, blob_name: str, container_name: str) -> bool:
        """
        Delete an asset from Azure Blob Storage

        Args:
            blob_name: Name of the blob to delete
            container_name: Name of the container

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name)
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return False

    def get_asset_url(self, blob_name: str, container_name: str) -> Optional[str]:
        """
        Get the URL for an asset

        Args:
            blob_name: Name of the blob
            container_name: Name of the container

        Returns:
            URL string or None if not found
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name)
            blob_client = container_client.get_blob_client(blob_name)
            # Check if blob exists
            blob_client.get_blob_properties()
            return blob_client.url
        except ResourceNotFoundError:
            return None

    def get_asset_content(self, blob_name: str, container_name: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Get the content of an asset

        Args:
            blob_name: Name of the blob
            container_name: Name of the container

        Returns:
            Tuple of (content as bytes, content type) or (None, None) if not found
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name)
            blob_client = container_client.get_blob_client(blob_name)

            # Get blob properties to check if it exists and get content type
            properties = blob_client.get_blob_properties()
            content_type = properties.content_settings.content_type

            # Download the blob
            download_stream = blob_client.download_blob()
            content = download_stream.readall()

            return content, content_type
        except ResourceNotFoundError:
            return None, None

    def list_folders(self, container_name: str) -> List[str]:
        """
        List all folders in a container

        Args:
            container_name: Name of the container to list folders from

        Returns:
            List of folder paths
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name)

            # Get all blobs
            blobs = container_client.list_blobs(include=['metadata'])

            # Extract unique folder paths
            folders = set()
            for blob in blobs:
                if "/" in blob.name:
                    # Extract the folder path
                    folder_path = "/".join(blob.name.split("/")[:-1]) + "/"
                    folders.add(folder_path)

                    # Also add parent folders
                    parts = folder_path.split("/")[:-1]
                    for i in range(1, len(parts)):
                        parent = "/".join(parts[:i]) + "/"
                        folders.add(parent)

            # Convert to sorted list
            return sorted(list(folders))
        except Exception:
            return []
