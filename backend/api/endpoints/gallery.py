from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form, Body, BackgroundTasks
from typing import Dict, List, Optional, Any
from fastapi.responses import StreamingResponse
import io
import re
import os
from datetime import datetime, timedelta, timezone
from azure.storage.blob import generate_container_sas, ContainerSasPermissions

from core.azure_storage import AzureBlobStorageService
from core.config import settings
from models.gallery import (
    GalleryResponse,
    GalleryItem,
    MediaType,
    AssetUploadResponse,
    AssetDeleteResponse,
    AssetUrlResponse,
    AssetMetadataResponse,
    MetadataUpdateRequest,
    SasTokenResponse
)

router = APIRouter()


@router.get("/", response_model=GalleryResponse)
async def get_gallery_items(
    limit: int = Query(
        50, description="Maximum number of items to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination"),
    continuation_token: Optional[str] = Query(
        None, description="Continuation token from previous response"),
    prefix: Optional[str] = Query(
        None, description="Optional prefix filter for filenames"),
    folder_path: Optional[str] = Query(
        None, description="Optional folder path to filter assets"),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Get all gallery items (images and videos) with pagination

    This endpoint combines results from both image and video containers.
    """
    try:
        # Normalize folder path and update prefix if folder_path is provided
        if folder_path is not None:
            normalized_folder = azure_storage_service.normalize_folder_path(
                folder_path)
            prefix = normalized_folder

        # Get images
        image_container = settings.AZURE_BLOB_IMAGE_CONTAINER
        image_results = azure_storage_service.list_blobs(
            container_name=image_container,
            prefix=prefix,
            limit=limit,
            marker=continuation_token,
            delimiter="/" if folder_path is not None else None
        )

        # Get videos
        video_container = settings.AZURE_BLOB_VIDEO_CONTAINER
        video_results = azure_storage_service.list_blobs(
            container_name=video_container,
            prefix=prefix,
            limit=limit,
            marker=continuation_token,
            delimiter="/" if folder_path is not None else None
        )

        # Combine results
        gallery_items = []

        # Process image results
        for blob in image_results["blobs"]:
            # Skip .folder files used as folder markers
            if blob["name"].endswith(".folder"):
                continue

            gallery_items.append(GalleryItem(
                id=blob["name"].split(".")[0].split(
                    "/")[-1],  # Extract UUID part
                name=blob["name"],
                media_type=MediaType.IMAGE,
                url=blob["url"],
                container=image_container,
                size=blob["size"],
                content_type=blob["content_type"],
                creation_time=blob["creation_time"],
                last_modified=blob["last_modified"],
                metadata=blob["metadata"],
                folder_path=blob.get("folder_path", "")
            ))

        # Process video results
        for blob in video_results["blobs"]:
            # Skip .folder files used as folder markers
            if blob["name"].endswith(".folder"):
                continue

            gallery_items.append(GalleryItem(
                id=blob["name"].split(".")[0].split(
                    "/")[-1],  # Extract UUID part
                name=blob["name"],
                media_type=MediaType.VIDEO,
                url=blob["url"],
                container=video_container,
                size=blob["size"],
                content_type=blob["content_type"],
                creation_time=blob["creation_time"],
                last_modified=blob["last_modified"],
                metadata=blob["metadata"],
                folder_path=blob.get("folder_path", "")
            ))

        # Sort by last_modified (newest first)
        gallery_items.sort(
            key=lambda x: x.last_modified if x.last_modified else "",
            reverse=True
        )

        # Apply offset and limit
        paginated_items = gallery_items[offset:offset+limit]

        # Get continuation token from either result (prefer the one that has more)
        continuation = None
        if image_results["continuation_token"] or video_results["continuation_token"]:
            continuation = (
                image_results["continuation_token"] if image_results["continuation_token"]
                else video_results["continuation_token"]
            )

        # Combine folder prefixes from both containers
        folders = set()
        if "prefixes" in image_results:
            folders.update(image_results["prefixes"])
        if "prefixes" in video_results:
            folders.update(video_results["prefixes"])

        return GalleryResponse(
            success=True,
            message="Gallery items retrieved successfully",
            total=len(gallery_items),
            limit=limit,
            offset=offset,
            items=paginated_items,
            continuation_token=continuation,
            folders=sorted(list(folders)) if folders else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/images", response_model=GalleryResponse)
async def get_gallery_images(
    limit: int = Query(
        50, description="Maximum number of items to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination"),
    continuation_token: Optional[str] = Query(
        None, description="Continuation token from previous response"),
    prefix: Optional[str] = Query(
        None, description="Optional prefix filter for filenames"),
    folder_path: Optional[str] = Query(
        None, description="Optional folder path to filter assets"),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """Get all gallery images with pagination"""
    try:
        # Normalize folder path and update prefix if folder_path is provided
        if folder_path is not None:
            normalized_folder = azure_storage_service.normalize_folder_path(
                folder_path)
            prefix = normalized_folder

        # Get images from the image container
        image_container = settings.AZURE_BLOB_IMAGE_CONTAINER
        results = azure_storage_service.list_blobs(
            container_name=image_container,
            prefix=prefix,
            limit=limit,
            marker=continuation_token,
            delimiter="/" if folder_path is not None else None
        )

        # Process image results
        gallery_items = []
        for blob in results["blobs"]:
            # Skip .folder files used as folder markers
            if blob["name"].endswith(".folder"):
                continue

            gallery_items.append(GalleryItem(
                id=blob["name"].split(".")[0].split(
                    "/")[-1],  # Extract UUID part
                name=blob["name"],
                media_type=MediaType.IMAGE,
                url=blob["url"],
                container=image_container,
                size=blob["size"],
                content_type=blob["content_type"],
                creation_time=blob["creation_time"],
                last_modified=blob["last_modified"],
                metadata=blob["metadata"],
                folder_path=blob.get("folder_path", "")
            ))

        return GalleryResponse(
            success=True,
            message="Gallery images retrieved successfully",
            total=len(gallery_items),
            limit=limit,
            offset=offset,
            items=gallery_items,
            continuation_token=results["continuation_token"],
            folders=results.get("prefixes")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos", response_model=GalleryResponse)
async def get_gallery_videos(
    limit: int = Query(
        50, description="Maximum number of items to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination"),
    continuation_token: Optional[str] = Query(
        None, description="Continuation token from previous response"),
    prefix: Optional[str] = Query(
        None, description="Optional prefix filter for filenames"),
    folder_path: Optional[str] = Query(
        None, description="Optional folder path to filter assets"),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """Get all gallery videos with pagination"""
    try:
        # Normalize folder path and update prefix if folder_path is provided
        if folder_path is not None:
            normalized_folder = azure_storage_service.normalize_folder_path(
                folder_path)
            prefix = normalized_folder

        # Get videos from the video container
        video_container = settings.AZURE_BLOB_VIDEO_CONTAINER
        results = azure_storage_service.list_blobs(
            container_name=video_container,
            prefix=prefix,
            limit=limit,
            marker=continuation_token,
            delimiter="/" if folder_path is not None else None
        )

        # Process video results
        gallery_items = []
        for blob in results["blobs"]:
            gallery_items.append(GalleryItem(
                id=blob["name"].split(".")[0].split(
                    "/")[-1],  # Extract UUID part
                name=blob["name"],
                media_type=MediaType.VIDEO,
                url=blob["url"],
                container=video_container,
                size=blob["size"],
                content_type=blob["content_type"],
                creation_time=blob["creation_time"],
                last_modified=blob["last_modified"],
                metadata=blob["metadata"],
                folder_path=blob.get("folder_path", "")
            ))

        return GalleryResponse(
            success=True,
            message="Gallery videos retrieved successfully",
            total=len(gallery_items),
            limit=limit,
            offset=offset,
            items=gallery_items,
            continuation_token=results["continuation_token"],
            folders=results.get("prefixes")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=AssetUploadResponse)
async def upload_asset(
    file: UploadFile = File(...),
    media_type: MediaType = Form(MediaType.IMAGE),
    metadata: Optional[str] = Form(None),
    folder_path: Optional[str] = Form(None),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Upload an asset (image or video) to Azure Blob Storage with optional metadata and folder

    Metadata can be provided as a JSON string in the form field.
    Example: metadata='{"author": "John Doe", "project": "Demo"}'

    The folder_path parameter specifies the folder to upload the asset to.
    Example: folder_path='vacation/2023'
    """
    try:
        # Validate file type
        if media_type == MediaType.IMAGE:
            valid_types = [".jpg", ".jpeg", ".png",
                           ".gif", ".webp", ".svg", ".bmp"]
        else:  # VIDEO
            valid_types = [".mp4", ".mov", ".avi", ".wmv", ".webm", ".mkv"]

        filename = file.filename.lower()
        if not any(filename.endswith(ext) for ext in valid_types):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Must be one of {', '.join(valid_types)}"
            )

        # Parse metadata if provided
        metadata_dict = None
        if metadata:
            try:
                import json
                metadata_dict = json.loads(metadata)

                # Ensure all metadata values are UTF-8 compatible strings
                if metadata_dict:
                    # We'll encode everything as UTF-8 and then decode back
                    # This ensures Azure Blob Storage can handle the metadata properly
                    for key, value in list(metadata_dict.items()):
                        if value is None:
                            # Remove None values as they can't be stored as metadata
                            del metadata_dict[key]
                        elif isinstance(value, (dict, list)):
                            # Convert complex types to JSON strings
                            metadata_dict[key] = json.dumps(value)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid JSON format for metadata"
                )

        # Upload to Azure Blob Storage
        result = await azure_storage_service.upload_asset(
            file,
            media_type.value,
            metadata=metadata_dict,
            folder_path=folder_path
        )

        return AssetUploadResponse(
            success=True,
            message=f"{media_type.value.capitalize()} uploaded successfully",
            **result
        )
    except Exception as e:
        import traceback
        error_detail = str(e)
        error_trace = traceback.format_exc()
        # Log the full error for debugging
        print(f"Upload error: {error_detail}")
        print(f"Error trace: {error_trace}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete", response_model=AssetDeleteResponse)
async def delete_asset(
    blob_name: str = Query(..., description="Name of the blob to delete"),
    media_type: MediaType = Query(
        None, description="Type of media (image or video) to determine container"),
    container: Optional[str] = Query(
        None, description="Container name (images or videos) - overrides media_type if provided"),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Delete an asset from Azure Blob Storage

    Provide either media_type or container. If both are provided, container takes precedence.
    """
    try:
        # Determine container name
        container_name = container
        if not container_name:
            if not media_type:
                raise HTTPException(
                    status_code=400,
                    detail="Either media_type or container must be specified"
                )
            container_name = settings.AZURE_BLOB_IMAGE_CONTAINER if media_type == MediaType.IMAGE else settings.AZURE_BLOB_VIDEO_CONTAINER

        # Delete from Azure Blob Storage
        success = azure_storage_service.delete_asset(blob_name, container_name)

        if not success:
            raise HTTPException(status_code=404, detail="Asset not found")

        return AssetDeleteResponse(
            success=True,
            message="Asset deleted successfully",
            blob_name=blob_name,
            container=container_name
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/metadata", response_model=AssetMetadataResponse)
async def update_asset_metadata(
    blob_name: str = Query(..., description="Name of the blob"),
    media_type: MediaType = Query(
        None, description="Type of media (image or video) to determine container"),
    container: Optional[str] = Query(
        None, description="Container name (images or videos) - overrides media_type if provided"),
    request: MetadataUpdateRequest = Body(...),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Update metadata for an existing asset

    This replaces all existing metadata with the new values.
    Provide either media_type or container. If both are provided, container takes precedence.
    """
    try:
        # Determine container name
        container_name = container
        if not container_name:
            if not media_type:
                raise HTTPException(
                    status_code=400,
                    detail="Either media_type or container must be specified"
                )
            container_name = settings.AZURE_BLOB_IMAGE_CONTAINER if media_type == MediaType.IMAGE else settings.AZURE_BLOB_VIDEO_CONTAINER

        # Convert complex types to strings
        metadata = {k: str(v) for k, v in request.metadata.items()}

        # Update metadata in Azure Blob Storage
        success = azure_storage_service.update_asset_metadata(
            blob_name, container_name, metadata)

        if not success:
            raise HTTPException(status_code=404, detail="Asset not found")

        return AssetMetadataResponse(
            success=True,
            blob_name=blob_name,
            container=container_name,
            metadata=metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/asset/{media_type}/{blob_name:path}")
async def get_asset_content(
    media_type: MediaType,
    blob_name: str,
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Stream asset content (image or video) directly from Azure Blob Storage

    This endpoint acts as a proxy to bypass CORS restrictions and authentication requirements
    for Azure Blob Storage assets.

    The blob_name parameter can include folder paths. 
    For example: folder/subfolder/image.jpg
    """
    try:
        # Determine container name based on media type
        container_name = settings.AZURE_BLOB_IMAGE_CONTAINER if media_type == MediaType.IMAGE else settings.AZURE_BLOB_VIDEO_CONTAINER

        # Get the asset content
        content, content_type = azure_storage_service.get_asset_content(
            blob_name, container_name)

        if not content:
            raise HTTPException(
                status_code=404, detail=f"Asset not found: {blob_name}")

        # Get just the filename without the folder path for the Content-Disposition header
        filename = blob_name.split('/')[-1] if '/' in blob_name else blob_name

        # Return the content as a streaming response
        return StreamingResponse(
            content=io.BytesIO(content),
            media_type=content_type,
            headers={"Content-Disposition": f"inline; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/folders", response_model=Dict[str, Any])
async def list_folders(
    media_type: Optional[MediaType] = Query(
        None, description="Filter folders by media type (image or video)"),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    List all folders in the storage

    This endpoint returns all folders in the image and/or video containers.
    """
    try:
        image_folders = []
        video_folders = []

        # Get folders based on media type filter
        if media_type is None or media_type == MediaType.IMAGE:
            image_container = settings.AZURE_BLOB_IMAGE_CONTAINER
            image_folders = azure_storage_service.list_folders(image_container)

        if media_type is None or media_type == MediaType.VIDEO:
            video_container = settings.AZURE_BLOB_VIDEO_CONTAINER
            video_folders = azure_storage_service.list_folders(video_container)

        # Combine folders
        all_folders = sorted(list(set(image_folders + video_folders)))

        # Organize into folder hierarchy
        folder_hierarchy = {}
        for folder in all_folders:
            parts = folder.strip('/').split('/')
            current = folder_hierarchy

            # Build the folder tree
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Last part
                    if part not in current:
                        current[part] = {}
                else:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

        return {
            "success": True,
            "message": "Folders retrieved successfully",
            "folders": all_folders,
            "folder_hierarchy": folder_hierarchy,
            "image_folders": image_folders if media_type is None else None,
            "video_folders": video_folders if media_type is None else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folders", response_model=Dict[str, Any])
async def create_folder(
    folder_path: str = Body(..., embed=True),
    media_type: MediaType = Body(MediaType.IMAGE, embed=True),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Create a new folder in the specified container

    This endpoint creates a folder marker in the container to represent an empty folder.
    Folders are virtual in Azure Blob Storage and are represented by blob name prefixes.
    """
    try:
        # Validate folder name (allow alphanumeric, hyphens, underscores, and slashes)
        folder_path = folder_path.strip()
        if not folder_path:
            raise HTTPException(
                status_code=400, detail="Folder path cannot be empty")

        # Remove leading/trailing slashes
        folder_path = folder_path.strip('/')

        # Basic validation - allow alphanumeric, hyphens, underscores, and slashes
        if not re.match(r'^[a-zA-Z0-9\-_/]+$', folder_path):
            raise HTTPException(
                status_code=400,
                detail="Folder path can only contain alphanumeric characters, hyphens, underscores, and slashes"
            )

        # Ensure folder ends with slash
        normalized_path = f"{folder_path}/"

        # Determine container based on media type
        container_name = settings.AZURE_BLOB_IMAGE_CONTAINER if media_type == MediaType.IMAGE else settings.AZURE_BLOB_VIDEO_CONTAINER

        # Create a placeholder/marker blob to represent the empty folder
        # Azure Blob Storage doesn't have actual folders, so we create a small marker file
        container_client = azure_storage_service.blob_service_client.get_container_client(
            container_name)
        blob_client = container_client.get_blob_client(
            f"{normalized_path}.folder")

        # Check if folder already exists
        existing_blobs = container_client.list_blobs(
            name_starts_with=normalized_path, results_per_page=1)
        try:
            next(existing_blobs)
            # If we get here, it means there's at least one blob with this prefix
            # We'll consider the folder as already existing
            return {
                "success": True,
                "message": "Folder already exists",
                "folder_path": normalized_path,
                "container": container_name,
                "created": False
            }
        except StopIteration:
            # No blobs with this prefix, we can create the folder
            pass

        # Upload an empty blob as a folder marker
        metadata = {
            "is_folder_marker": "true",
            "folder_path": normalized_path
        }
        blob_client.upload_blob(data=b"", overwrite=True, metadata=metadata)

        return {
            "success": True,
            "message": "Folder created successfully",
            "folder_path": normalized_path,
            "container": container_name,
            "created": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _move_asset_background(
    blob_name: str,
    container_name: str,
    target_folder: str,
    azure_storage_service: AzureBlobStorageService
):
    """Background task to move an asset to a different folder"""
    try:
        # Get original blob content and metadata
        content, content_type = azure_storage_service.get_asset_content(
            blob_name, container_name)
        if not content:
            print(f"Error: Asset content not found: {blob_name}")
            return False

        # Get metadata
        metadata = azure_storage_service.get_asset_metadata(
            blob_name, container_name) or {}

        # Create new blob name with target folder
        file_name = blob_name.split('/')[-1] if '/' in blob_name else blob_name
        normalized_folder = azure_storage_service.normalize_folder_path(
            target_folder)
        new_blob_name = f"{normalized_folder}{file_name}"

        # Create blob client for new location
        container_client = azure_storage_service.blob_service_client.get_container_client(
            container_name)
        blob_client = container_client.get_blob_client(new_blob_name)

        # Update metadata with new folder path
        metadata['folder_path'] = normalized_folder

        # Set content type
        from azure.storage.blob import ContentSettings
        content_settings = ContentSettings(content_type=content_type)

        # Upload to new location
        blob_client.upload_blob(data=content, overwrite=True,
                                metadata=metadata, content_settings=content_settings)

        # Delete original blob after successful copy
        azure_storage_service.delete_asset(blob_name, container_name)

        print(f"Successfully moved asset from {blob_name} to {new_blob_name}")
        return True
    except Exception as e:
        print(f"Error moving asset in background: {str(e)}")
        return False


@router.put("/move", response_model=Dict[str, Any])
async def move_asset(
    background_tasks: BackgroundTasks,
    blob_name: str = Body(..., embed=True),
    container: str = Body(None, embed=True),
    media_type: MediaType = Body(None, embed=True),
    target_folder: str = Body(..., embed=True),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Move an asset to a different folder

    This operation creates a copy of the asset in the target folder and then 
    deletes the original. For large files, this happens as a background task.

    Provide either container or media_type. If both are provided, container takes precedence.
    """
    try:
        # Validate parameters
        if not blob_name:
            raise HTTPException(
                status_code=400, detail="Blob name is required")

        # Normalize target folder
        normalized_folder = azure_storage_service.normalize_folder_path(
            target_folder)

        # Determine container name
        container_name = container
        if not container_name:
            if not media_type:
                raise HTTPException(
                    status_code=400,
                    detail="Either media_type or container must be specified"
                )
            container_name = settings.AZURE_BLOB_IMAGE_CONTAINER if media_type == MediaType.IMAGE else settings.AZURE_BLOB_VIDEO_CONTAINER

        # Check if source blob exists
        metadata = azure_storage_service.get_asset_metadata(
            blob_name, container_name)
        if not metadata:
            raise HTTPException(
                status_code=404, detail="Source asset not found")

        # Get the file size to determine if we should use background task
        file_name = blob_name.split('/')[-1] if '/' in blob_name else blob_name
        new_blob_name = f"{normalized_folder}{file_name}"

        # Check if target folder exists
        container_client = azure_storage_service.blob_service_client.get_container_client(
            container_name)
        folders = azure_storage_service.list_folders(container_name)
        if normalized_folder not in folders and normalized_folder != "":
            # Create marker for folder
            folder_marker = f"{normalized_folder}.folder"
            marker_metadata = {
                "is_folder_marker": "true",
                "folder_path": normalized_folder
            }
            folder_blob_client = container_client.get_blob_client(
                folder_marker)
            folder_blob_client.upload_blob(
                data=b"", overwrite=True, metadata=marker_metadata)

        # Check if target already exists (to avoid overwrite if interrupted)
        try:
            container_client.get_blob_client(
                new_blob_name).get_blob_properties()
            # If we get here, the target already exists
            raise HTTPException(
                status_code=400, detail="Target file already exists")
        except:
            # Target doesn't exist, which is what we want
            pass

        # Check if source and target are the same
        current_folder = ""
        if "/" in blob_name:
            current_folder = "/".join(blob_name.split("/")[:-1]) + "/"

        if current_folder == normalized_folder:
            return {
                "success": True,
                "message": "Asset is already in the target folder",
                "moved": False,
                "background_task": False
            }

        # For files larger than 10MB, use background task
        content, _ = azure_storage_service.get_asset_content(
            blob_name, container_name)
        use_background = len(content) > 10 * 1024 * 1024  # 10MB

        if use_background:
            # Move in background
            background_tasks.add_task(
                _move_asset_background,
                blob_name,
                container_name,
                target_folder,
                azure_storage_service
            )
            return {
                "success": True,
                "message": "Asset move started in background",
                "source": blob_name,
                "destination": new_blob_name,
                "moved": True,
                "background_task": True
            }
        else:
            # Move synchronously
            await _move_asset_background(blob_name, container_name, target_folder, azure_storage_service)
            return {
                "success": True,
                "message": "Asset moved successfully",
                "source": blob_name,
                "destination": new_blob_name,
                "moved": True,
                "background_task": False
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sas-tokens", response_model=SasTokenResponse)
async def get_sas_tokens():
    """Generate and return SAS tokens for frontend direct access to blob storage"""
    try:
        # Generate image token with read-only permissions, valid for 1 hour
        image_token = generate_container_sas(
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=settings.AZURE_BLOB_IMAGE_CONTAINER,
            account_key=settings.AZURE_STORAGE_ACCOUNT_KEY,
            permission=ContainerSasPermissions(
                read=True),  # Read-only for frontend
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Return token and container URL
        expiry_time = datetime.now(timezone.utc) + timedelta(hours=1)
        return {
            "success": True,
            "message": "SAS token generated successfully",
            "image_sas_token": image_token,
            "image_container_url": f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{settings.AZURE_BLOB_IMAGE_CONTAINER}",
            "expiry": expiry_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
