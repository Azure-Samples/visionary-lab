import os
import uuid
from typing import Dict, BinaryIO, Optional, Union, List, Tuple
from fastapi import UploadFile
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from datetime import datetime

from core.config import settings


class AzureBlobStorageService:
    """Service for handling Azure Blob Storage operations"""

    def __init__(self):
        """Initialize Azure Blob Storage client"""
        self.image_container = settings.AZURE_BLOB_IMAGE_CONTAINER

        # Create the BlobServiceClient using either connection string or account credentials
        if settings.AZURE_STORAGE_CONNECTION_STRING:
            # Create client using connection string (deprecated approach)
            self.blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING)
        else:
            # Create client using account name and key (preferred approach)
            account_url = settings.AZURE_BLOB_SERVICE_URL
            # If AZURE_BLOB_SERVICE_URL is not provided, construct it from account name
            if not account_url and settings.AZURE_STORAGE_ACCOUNT_NAME:
                account_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/"

            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=settings.AZURE_STORAGE_ACCOUNT_KEY
            )

        # Ensure container exists
        self._ensure_container_exists(self.image_container)

    def list_blobs(self, container_name: str, prefix: Optional[str] = None,
                   limit: int = 100, marker: Optional[str] = None,
                   delimiter: Optional[str] = None) -> Dict:
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
                # Important: explicitly request metadata
                "include": ['metadata']
            }

            # Only add delimiter if it's supported in this version of the SDK
            # Some versions of the Azure Storage SDK might not support this parameter
            try:
                import inspect
                # Check if the method accepts the delimiter parameter
                sig = inspect.signature(container_client.list_blobs)
                if 'delimiter' in sig.parameters:
                    list_params["delimiter"] = delimiter
            except:
                # If there's any error checking, we'll just skip the delimiter
                pass

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

            # If delimiter is provided and supported, also extract prefixes (folder names)
            prefixes = []
            if hasattr(blobs_page, 'prefix') and blobs_page.prefix:
                prefixes = [p for p in blobs_page.prefix]

            return {
                "blobs": blob_list,
                "continuation_token": continuation_token,
                "container": container_name,
                "prefixes": prefixes
            }

        except ResourceNotFoundError:
            # Return empty list if container doesn't exist
            return {
                "blobs": [],
                "continuation_token": None,
                "container": container_name,
                "prefixes": []
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

    def _preprocess_metadata_value(self, value: str) -> str:
        """
        Preprocess metadata value to comply with Azure Blob Storage requirements.
        Removes newlines, tabs, and other invalid characters.

        Args:
            value: Metadata value to preprocess

        Returns:
            Processed string compatible with Azure Blob Storage
        """
        if value is None:
            return ""

        # Convert to string if not already
        str_value = str(value)

        # Replace newlines and tabs with spaces
        str_value = str_value.replace('\n', ' ').replace(
            '\r', ' ').replace('\t', ' ')

        # Collapse multiple spaces into a single space
        import re
        str_value = re.sub(r'\s+', ' ', str_value)

        # Trim leading/trailing whitespace
        str_value = str_value.strip()

        # Try to encode as Latin-1 as required by Azure
        try:
            str_value.encode('latin-1')
            return str_value
        except UnicodeEncodeError:
            # Replace any non-Latin-1 characters
            ascii_value = str_value.encode('ascii', 'replace').decode('ascii')
            return ascii_value

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
    
    

    async def upload_asset(self, file: UploadFile, asset_type: str = "image",
                           metadata: Optional[Dict[str, str]] = None,
                           folder_path: Optional[str] = None) -> Dict[str, str]:
        """
        Upload an asset (image or video) to Azure Blob Storage

        Args:
            file: The uploaded file
            asset_type: Type of asset ("image" or "video")
            metadata: Optional metadata as key-value pairs
            folder_path: Optional folder path to store the asset in

        Returns:
            Dictionary with asset information
        """
        try:
            # Always use image container
            container_name = self.image_container

            # Generate a unique ID for the file
            file_id = str(uuid.uuid4())

            # Get file extension and determine content type
            _, ext = os.path.splitext(file.filename)
            content_type = self._get_content_type(ext, asset_type)

            # Normalize folder path
            normalized_folder_path = self.normalize_folder_path(folder_path)

            # Create blob name with optional folder path and UUID
            blob_name = f"{normalized_folder_path}{file_id}{ext}"

            # Get container client
            container_client = self.blob_service_client.get_container_client(
                container_name)

            # Create blob client
            blob_client = container_client.get_blob_client(blob_name)

            # Set content settings
            content_settings = ContentSettings(content_type=content_type)

            # Prepare metadata (all values must be strings)
            upload_metadata = {}
            if metadata:
                # Process each metadata value to make it Azure-compatible
                for k, v in metadata.items():
                    # Skip None values
                    if v is None:
                        continue

                    # Process the value to make it Azure-compatible
                    processed_value = self._preprocess_metadata_value(v)
                    upload_metadata[k] = processed_value

            # Add folder path to metadata if it exists
            if normalized_folder_path:
                upload_metadata["folder_path"] = normalized_folder_path

            # Upload the file
            file_content = await file.read()
            blob_client.upload_blob(
                data=file_content,
                content_settings=content_settings,
                metadata=upload_metadata,
                overwrite=True
            )

            # Get the blob URL
            blob_url = blob_client.url

            return {
                "file_id": file_id,
                "blob_name": blob_name,
                "container": container_name,
                "url": blob_url,
                "size": len(file_content),
                "content_type": content_type,
                "original_filename": file.filename,
                "metadata": upload_metadata,
                "folder_path": normalized_folder_path
            }
        except Exception as e:
            import traceback
            print(f"Azure upload error: {str(e)}")
            print(f"Error trace: {traceback.format_exc()}")
            raise

    def get_asset_metadata(self, blob_name: str, container_name: str) -> Optional[Dict[str, str]]:
        """
        Get metadata for an asset

        Args:
            blob_name: Name of the blob
            container_name: Name of the container

        Returns:
            Dictionary of metadata or None if not found
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name)
            blob_client = container_client.get_blob_client(blob_name)

            # Get blob properties which includes metadata
            properties = blob_client.get_blob_properties()
            # Return empty dict instead of None for consistency
            return properties.metadata or {}
        except ResourceNotFoundError:
            return None

    def update_asset_metadata(self, blob_name: str, container_name: str, metadata: Dict[str, str]) -> bool:
        """
        Update metadata for an existing blob

        Args:
            blob_name: Name of the blob
            container_name: Name of the container
            metadata: New metadata to set (completely replaces existing metadata)

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name)
            blob_client = container_client.get_blob_client(blob_name)

            # Convert all values to strings compatible with Azure's Latin-1 requirement
            metadata_str = {}
            for k, v in metadata.items():
                # Skip None values
                if v is None:
                    continue

                # Ensure value is string
                str_value = str(v)

                # Convert to ASCII-safe string if needed
                try:
                    # Test if it can be encoded as Latin-1 (required by Azure)
                    str_value.encode('latin-1')
                    # If successful, use the original string
                    metadata_str[k] = str_value
                except UnicodeEncodeError:
                    # If it fails, replace problematic characters
                    ascii_value = str_value.encode(
                        'ascii', 'replace').decode('ascii')
                    metadata_str[k] = ascii_value
                    print(
                        f"Converted Unicode metadata for key '{k}': '{str_value}' -> '{ascii_value}'")

            # Set metadata (replaces all existing metadata)
            blob_client.set_blob_metadata(metadata=metadata_str)
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            import traceback
            print(f"Metadata update error: {str(e)}")
            print(f"Error trace: {traceback.format_exc()}")
            return False

    def _get_content_type(self, extension: str, asset_type: str) -> str:
        """
        Determine content type based on file extension

        Args:
            extension: File extension including the dot
            asset_type: Type of asset ("image" or "video")

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

        # Video content types
        video_types = {
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".wmv": "video/x-ms-wmv",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska"
        }

        if asset_type == "image":
            return image_types.get(extension, "application/octet-stream")
        else:
            return video_types.get(extension, "application/octet-stream")

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
        except Exception as e:
            print(f"Error listing folders: {str(e)}")
            return []
