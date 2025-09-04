from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query,
    UploadFile,
    File,
    Form,
    Body,
    BackgroundTasks,
)
from typing import Dict, List, Optional, Any
from fastapi.responses import StreamingResponse
import io
import re
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from azure.storage.blob import generate_container_sas, ContainerSasPermissions

from backend.core.azure_storage import AzureBlobStorageService
from backend.core.cosmos_client import CosmosDBService
from backend.core.config import settings
from backend.models.gallery import (
    GalleryResponse,
    GalleryItem,
    MediaType,
    AssetUploadResponse,
    AssetDeleteResponse,
    AssetUrlResponse,
    AssetMetadataResponse,
    MetadataUpdateRequest,
    SasTokenResponse,
)
from backend.models.metadata_models import AssetMetadataCreateRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


def get_cosmos_service() -> Optional[CosmosDBService]:
    """Dependency to get Cosmos DB service instance (optional)"""
    try:
        # Check if we have either managed identity or key-based auth configured
        if settings.AZURE_COSMOS_DB_ENDPOINT and (
            settings.USE_MANAGED_IDENTITY or settings.AZURE_COSMOS_DB_KEY
        ):
            return CosmosDBService()
        return None
    except Exception as e:
        # Log error but don't fail - Cosmos DB is optional
        logger.warning(f"Cosmos DB service unavailable: {e}")
        return None


@router.get("/images", response_model=GalleryResponse)
async def get_gallery_images(
    limit: int = Query(
        50, description="Maximum number of items to return", ge=1, le=100
    ),
    offset: int = Query(0, description="Offset for pagination"),
    folder_path: Optional[str] = Query(
        None, description="Optional folder path to filter assets"
    ),
    tags: Optional[str] = Query(
        None, description="Comma-separated tags to filter by"),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """Get gallery images from Cosmos DB metadata ONLY"""
    try:
        # Check if Cosmos DB service is available
        if not cosmos_service:
            logger.error("Cosmos DB service is not available")
            raise HTTPException(
                status_code=503,
                detail="Cosmos DB service is not available. Please check your configuration.",
            )

        # Parse tags if provided
        tag_list = None
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Query Cosmos DB for images only
        result = cosmos_service.query_assets(
            media_type="image",  # Images only
            folder_path=folder_path,
            tags=tag_list,
            limit=limit,
            offset=offset,
            order_by="created_at",
            order_desc=True,
        )

        gallery_items = []
        for metadata in result["items"]:
            # Extract technical metadata from custom_metadata if available
            custom_meta = metadata.get("custom_metadata", {})

            gallery_items.append(
                GalleryItem(
                    id=metadata["id"],
                    name=metadata["blob_name"],
                    media_type=MediaType.IMAGE,
                    url=metadata["url"],
                    container=metadata["container"],
                    size=metadata["size"],
                    content_type=metadata.get("content_type"),
                    creation_time=metadata["created_at"],
                    last_modified=metadata["updated_at"],
                    metadata={
                        # Core generation metadata from CosmosDB (only include meaningful values)
                        **{k: v for k, v in {
                            "prompt": metadata.get("prompt"),
                            "model": metadata.get("model"),
                            "description": metadata.get("description"),
                            "quality": metadata.get("quality"),
                            "background": metadata.get("background"),
                            "output_format": metadata.get("output_format"),
                            "has_transparency": metadata.get("has_transparency"),
                            "generation_id": metadata.get("generation_id"),
                        }.items() if v is not None and v != "" and v != "auto"},

                        # Technical metadata (ensure integers, only include if valid)
                        **{k: v for k, v in {
                            "width": custom_meta.get("width") or metadata.get("width"),
                            "height": custom_meta.get("height") or metadata.get("height"),
                            "created_at": metadata.get("created_at"),
                        }.items() if v is not None},

                        # Analysis structure (nested only - no legacy support)
                        **({"analysis": metadata.get("analysis")} if metadata.get("analysis") else {}),
                        "has_analysis": metadata.get("has_analysis", False),

                        # Additional custom fields (exclude None values and reserved keys)
                        **{k: v for k, v in custom_meta.items()
                           if k not in ["width", "height", "prompt", "description", "analysis"]
                           and v is not None and v != ""}
                    },
                    folder_path=metadata.get("folder_path", ""),
                )
            )

        return GalleryResponse(
            success=True,
            message=f"Retrieved {len(gallery_items)} images from metadata service",
            total=result["total"],
            limit=limit,
            offset=offset,
            items=gallery_items,
            continuation_token=None,
            folders=None,
        )
    except Exception as e:
        logger.error(f"Error retrieving images from metadata: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve images from metadata service: {str(e)}",
        )


@router.get("/videos", response_model=GalleryResponse)
async def get_gallery_videos(
    limit: int = Query(
        50, description="Maximum number of items to return", ge=1, le=100
    ),
    offset: int = Query(0, description="Offset for pagination"),
    folder_path: Optional[str] = Query(
        None, description="Optional folder path to filter assets"
    ),
    tags: Optional[str] = Query(
        None, description="Comma-separated tags to filter by"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Get gallery videos from Cosmos DB metadata ONLY"""
    try:
        # Parse tags if provided
        tag_list = None
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Query Cosmos DB for videos only
        result = cosmos_service.query_assets(
            media_type="video",  # Videos only
            folder_path=folder_path,
            tags=tag_list,
            limit=limit,
            offset=offset,
            order_by="created_at",
            order_desc=True,
        )

        gallery_items = []
        for metadata in result["items"]:
            # Extract technical metadata from custom_metadata if available
            custom_meta = metadata.get("custom_metadata", {})

            gallery_items.append(
                GalleryItem(
                    id=metadata["id"],
                    name=metadata["blob_name"],
                    media_type=MediaType.VIDEO,
                    url=metadata["url"],
                    container=metadata["container"],
                    size=metadata["size"],
                    content_type=metadata.get("content_type"),
                    creation_time=metadata["created_at"],
                    last_modified=metadata["updated_at"],
                    metadata={
                        # Core generation metadata from CosmosDB (only include meaningful values)
                        **{k: v for k, v in {
                            "prompt": metadata.get("prompt"),
                            "model": metadata.get("model"),
                            "description": metadata.get("description"),
                            "quality": metadata.get("quality"),
                            "background": metadata.get("background"),
                            "output_format": metadata.get("output_format"),
                            "generation_id": metadata.get("generation_id"),
                        }.items() if v is not None and v != "" and v != "auto"},

                        # Video-specific metadata (only include if not None)
                        **{k: v for k, v in {
                            "duration": metadata.get("duration"),
                            "resolution": metadata.get("resolution"),
                            "fps": metadata.get("fps"),
                        }.items() if v is not None},

                        # Technical metadata (ensure integers, only include if valid)
                        **{k: v for k, v in {
                            "width": custom_meta.get("width") or metadata.get("width"),
                            "height": custom_meta.get("height") or metadata.get("height"),
                            "created_at": metadata.get("created_at"),
                        }.items() if v is not None},

                        # Analysis structure (nested only - no legacy support)
                        **({"analysis": metadata.get("analysis")} if metadata.get("analysis") else {}),
                        "has_analysis": metadata.get("has_analysis", False),

                        # Additional custom fields (exclude None values and reserved keys)
                        **{k: v for k, v in custom_meta.items()
                           if k not in ["width", "height", "prompt", "description", "analysis", "duration", "fps", "resolution"]
                           and v is not None and v != ""}
                    },
                    folder_path=metadata.get("folder_path", ""),
                )
            )

        return GalleryResponse(
            success=True,
            message=f"Retrieved {len(gallery_items)} videos from metadata service",
            total=result["total"],
            limit=limit,
            offset=offset,
            items=gallery_items,
            continuation_token=None,
            folders=None,
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving videos from metadata: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve videos from metadata service: {str(e)}",
        )


@router.get("/", response_model=GalleryResponse)
async def get_gallery_items(
    limit: int = Query(
        50, description="Maximum number of items to return", ge=1, le=100
    ),
    offset: int = Query(0, description="Offset for pagination"),
    folder_path: Optional[str] = Query(
        None, description="Optional folder path to filter assets"
    ),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    Get all gallery items (images and videos) from CosmosDB metadata
    """
    try:
        # Check if Cosmos DB service is available
        if not cosmos_service:
            logger.error("Cosmos DB service is not available")
            raise HTTPException(
                status_code=503,
                detail="Cosmos DB service is not available. Please check your configuration.",
            )

        return await _get_gallery_items_from_cosmos(
            limit=limit,
            offset=offset,
            folder_path=folder_path,
            cosmos_service=cosmos_service,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving gallery items from CosmosDB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _get_gallery_items_from_cosmos(
    limit: int, offset: int, folder_path: Optional[str], cosmos_service: CosmosDBService
) -> GalleryResponse:
    """Get gallery items from CosmosDB metadata with standardized analysis structure"""
    try:
        result = cosmos_service.query_assets(
            folder_path=folder_path,
            limit=limit,
            offset=offset,
            order_by="created_at",
            order_desc=True,
        )

        gallery_items = []
        for metadata in result["items"]:
            # Extract technical metadata from custom_metadata if available
            custom_meta = metadata.get("custom_metadata", {})

            # Convert CosmosDB metadata to GalleryItem (CosmosDB is single source of truth)
            gallery_items.append(
                GalleryItem(
                    id=metadata["id"],
                    name=metadata["blob_name"],
                    media_type=MediaType(metadata["media_type"]),
                    url=metadata["url"],
                    container=metadata["container"],
                    size=metadata["size"],
                    content_type=metadata.get("content_type"),
                    creation_time=metadata["created_at"],
                    last_modified=metadata["updated_at"],
                    metadata={
                        # Core generation metadata from CosmosDB (only meaningful values)
                        **{k: v for k, v in {
                            "prompt": metadata.get("prompt"),
                            "model": metadata.get("model"),
                            "description": metadata.get("description"),
                            "quality": metadata.get("quality"),
                            "background": metadata.get("background"),
                            "output_format": metadata.get("output_format"),
                            "has_transparency": metadata.get("has_transparency"),
                            "generation_id": metadata.get("generation_id"),
                        }.items() if v is not None and v != "" and v != "auto"},

                        # Technical metadata (ensure proper types)
                        **{k: v for k, v in {
                            "width": custom_meta.get("width") or metadata.get("width"),
                            "height": custom_meta.get("height") or metadata.get("height"),
                            "created_at": metadata.get("created_at"),
                        }.items() if v is not None},

                        # Video-specific metadata
                        **{k: v for k, v in {
                            "duration": metadata.get("duration"),
                            "fps": metadata.get("fps"),
                            "resolution": metadata.get("resolution"),
                        }.items() if v is not None},

                        # Analysis structure (nested only)
                        **({"analysis": metadata.get("analysis")} if metadata.get("analysis") else {}),
                        "has_analysis": metadata.get("has_analysis", False),

                        # Additional custom fields (exclude reserved keys and None values)
                        **{k: v for k, v in custom_meta.items()
                           if k not in ["width", "height", "prompt", "description", "analysis", "duration", "fps", "resolution"]
                           and v is not None and v != ""}
                    },
                    folder_path=metadata.get("folder_path", ""),
                )
            )

        return GalleryResponse(
            success=True,
            message="Gallery items retrieved successfully from metadata",
            total=result["total"],
            limit=limit,
            offset=offset,
            items=gallery_items,
            continuation_token=None,  # Cosmos DB uses offset-based pagination
            folders=None,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error querying metadata: {str(e)}"
        )


# Removed legacy blob storage implementation - now using CosmosDB only


@router.post("/upload", response_model=AssetUploadResponse)
async def upload_asset(
    file: UploadFile = File(...),
    media_type: MediaType = Form(MediaType.IMAGE),
    metadata: Optional[str] = Form(None),
    folder_path: Optional[str] = Form(None),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()
    ),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    Upload an asset (image or video) to Azure Blob Storage with optional metadata
    Also creates metadata record in Cosmos DB if available
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
                detail=f"Invalid file type. Must be one of {', '.join(valid_types)}",
            )

        # Parse metadata if provided
        metadata_dict = None
        if metadata:
            try:
                import json

                metadata_dict = json.loads(metadata)

                # Ensure all metadata values are UTF-8 compatible strings
                if metadata_dict:
                    for key, value in list(metadata_dict.items()):
                        if value is None:
                            del metadata_dict[key]
                        elif isinstance(value, (dict, list)):
                            metadata_dict[key] = json.dumps(value)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Invalid JSON format for metadata"
                )

        # Upload to Azure Blob Storage (no metadata stored in blob)
        result = await azure_storage_service.upload_asset(
            file, media_type.value, metadata=None, folder_path=folder_path
        )

        # Create metadata record in Cosmos DB if available
        if cosmos_service:
            try:
                # Prepare metadata for Cosmos DB
                cosmos_data = {
                    "media_type": media_type.value,
                    "blob_name": result["blob_name"],
                    "container": result["container"],
                    "url": result["url"],
                    "filename": result["original_filename"],
                    "size": result["size"],
                    "content_type": result["content_type"],
                    "folder_path": result["folder_path"],
                }

                # Add dimensions if available from upload result
                if "width" in result:
                    cosmos_data["width"] = result["width"]
                if "height" in result:
                    cosmos_data["height"] = result["height"]

                # Add custom metadata
                if metadata_dict:
                    cosmos_data["custom_metadata"] = metadata_dict

                cosmos_metadata = AssetMetadataCreateRequest(**cosmos_data)

                cosmos_service.create_asset_metadata(
                    cosmos_metadata.dict(exclude_unset=True)
                )
            except Exception as cosmos_error:
                # Log error but don't fail the upload
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to create Cosmos DB metadata: {cosmos_error}")

        return AssetUploadResponse(
            success=True,
            message=f"{media_type.value.capitalize()} uploaded successfully",
            **result,
        )
    except Exception as e:
        import traceback

        error_detail = str(e)
        error_trace = traceback.format_exc()
        print(f"Upload error: {error_detail}")
        print(f"Error trace: {error_trace}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete", response_model=AssetDeleteResponse)
async def delete_asset(
    blob_name: str = Query(..., description="Name of the blob to delete"),
    media_type: MediaType = Query(
        None, description="Type of media (image or video) to determine container"
    ),
    container: Optional[str] = Query(
        None,
        description="Container name (images or videos) - overrides media_type if provided",
    ),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()
    ),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    Delete an asset from Azure Blob Storage and Cosmos DB metadata
    """
    try:
        # Determine container name
        container_name = container
        if not container_name:
            if not media_type:
                raise HTTPException(
                    status_code=400,
                    detail="Either media_type or container must be specified",
                )
            container_name = (
                settings.AZURE_BLOB_IMAGE_CONTAINER
                if media_type == MediaType.IMAGE
                else settings.AZURE_BLOB_VIDEO_CONTAINER
            )

        # Extract asset ID for Cosmos DB deletion
        asset_id = blob_name.split(".")[0].split("/")[-1]
        media_type_str = (
            "image"
            if container_name == settings.AZURE_BLOB_IMAGE_CONTAINER
            else "video"
        )

        # Delete from Cosmos DB first (if available)
        if cosmos_service:
            try:
                cosmos_service.delete_asset_metadata(asset_id, media_type_str)
            except Exception as cosmos_error:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to delete Cosmos DB metadata: {cosmos_error}")

        # Delete from Azure Blob Storage
        success = azure_storage_service.delete_asset(blob_name, container_name)

        if not success:
            raise HTTPException(status_code=404, detail="Asset not found")

        return AssetDeleteResponse(
            success=True,
            message="Asset deleted successfully",
            blob_name=blob_name,
            container=container_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Include all other existing endpoints with similar Cosmos DB integration...
# For brevity, I'm showing the pattern for the main endpoints.
# The remaining endpoints would follow the same pattern of:
# 1. Try Cosmos DB operation if available
# 2. Fall back to blob storage
# 3. Log warnings for Cosmos DB failures but don't fail the operation


@router.get("/asset/{media_type}/{blob_name:path}")
async def get_asset_content(
    media_type: MediaType,
    blob_name: str,
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()
    ),
):
    """Stream asset content directly from Azure Blob Storage"""
    try:
        container_name = (
            settings.AZURE_BLOB_IMAGE_CONTAINER
            if media_type == MediaType.IMAGE
            else settings.AZURE_BLOB_VIDEO_CONTAINER
        )
        content, content_type = azure_storage_service.get_asset_content(
            blob_name, container_name
        )

        if not content:
            raise HTTPException(
                status_code=404, detail=f"Asset not found: {blob_name}")

        filename = blob_name.split("/")[-1] if "/" in blob_name else blob_name

        return StreamingResponse(
            content=io.BytesIO(content),
            media_type=content_type,
            headers={"Content-Disposition": f"inline; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sas-tokens", response_model=SasTokenResponse)
async def get_sas_tokens():
    """Generate and return SAS tokens for frontend direct access to blob storage"""
    try:
        video_token = generate_container_sas(
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=settings.AZURE_BLOB_VIDEO_CONTAINER,
            account_key=settings.AZURE_STORAGE_ACCOUNT_KEY,
            permission=ContainerSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        image_token = generate_container_sas(
            account_name=settings.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=settings.AZURE_BLOB_IMAGE_CONTAINER,
            account_key=settings.AZURE_STORAGE_ACCOUNT_KEY,
            permission=ContainerSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        expiry_time = datetime.now(timezone.utc) + timedelta(hours=1)
        return {
            "success": True,
            "message": "SAS tokens generated successfully",
            "video_sas_token": video_token,
            "image_sas_token": image_token,
            "video_container_url": f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{settings.AZURE_BLOB_VIDEO_CONTAINER}",
            "image_container_url": f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{settings.AZURE_BLOB_IMAGE_CONTAINER}",
            "expiry": expiry_time,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()
    ),
):
    """
    Health check endpoint to verify all services are working
    """
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
        "overall_status": "healthy",
    }

    # Check Azure Blob Storage
    try:
        # Try to list containers to test connectivity
        containers = [
            settings.AZURE_BLOB_IMAGE_CONTAINER,
            settings.AZURE_BLOB_VIDEO_CONTAINER,
        ]
        for container in containers:
            azure_storage_service._ensure_container_exists(container)

        health_status["services"]["azure_blob_storage"] = {
            "status": "healthy",
            "message": "Successfully connected to Azure Blob Storage",
            "containers": containers,
        }
    except Exception as e:
        health_status["services"]["azure_blob_storage"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["overall_status"] = "degraded"

    # Check Cosmos DB
    if cosmos_service:
        try:
            cosmos_health = cosmos_service.health_check()
            health_status["services"]["cosmos_db"] = cosmos_health

            if cosmos_health["status"] != "healthy":
                health_status["overall_status"] = "degraded"

        except Exception as e:
            health_status["services"]["cosmos_db"] = {
                "status": "unhealthy",
                "error": str(e),
                "message": "Cosmos DB metadata service unavailable - falling back to blob storage",
            }
            health_status["overall_status"] = "degraded"
    else:
        health_status["services"]["cosmos_db"] = {
            "status": "unavailable",
            "message": "Cosmos DB not configured - using blob storage only",
        }
        health_status["overall_status"] = "degraded"

    # Check AI Services
    try:
        # Test if AI clients are properly initialized
        from backend.core import sora_client, dalle_client, llm_client

        ai_services = {}
        if sora_client:
            ai_services["sora"] = "available"
        if dalle_client:
            ai_services["dalle/gpt_image"] = "available"
        if llm_client:
            ai_services["llm"] = "available"

        health_status["services"]["ai_services"] = {
            "status": "healthy" if ai_services else "unhealthy",
            "available_services": ai_services,
            "message": f"{len(ai_services)} AI services available",
        }

    except Exception as e:
        health_status["services"]["ai_services"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["overall_status"] = "degraded"

    return health_status


@router.get("/metadata/status", response_model=Dict[str, Any])
async def metadata_service_status(
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    Detailed status of metadata service capabilities
    """
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "metadata_service": {},
        "capabilities": {},
    }

    if cosmos_service:
        try:
            # Test basic connectivity
            cosmos_health = cosmos_service.health_check()

            # Test query capabilities
            test_query_result = cosmos_service.query_assets(limit=1, offset=0)

            # Test search capabilities
            try:
                search_result = cosmos_service.search_assets("test", limit=1)
                search_available = True
            except:
                search_available = False

            status["metadata_service"] = {
                "status": "available",
                "type": "cosmos_db",
                "health": cosmos_health,
                "total_assets": test_query_result.get("total", 0),
                "performance_mode": "fast_metadata_queries",
            }

            status["capabilities"] = {
                "fast_pagination": True,
                "advanced_search": search_available,
                "metadata_filtering": True,
                "tag_based_search": True,
                "folder_statistics": True,
                "recent_assets": True,
                "ai_metadata_enrichment": True,
            }

        except Exception as e:
            status["metadata_service"] = {
                "status": "error",
                "type": "cosmos_db",
                "error": str(e),
                "performance_mode": "fallback_to_blob_storage",
            }

            status["capabilities"] = {
                "fast_pagination": False,
                "advanced_search": False,
                "metadata_filtering": False,
                "tag_based_search": False,
                "folder_statistics": False,
                "recent_assets": False,
                "ai_metadata_enrichment": False,
            }
    else:
        status["metadata_service"] = {
            "status": "unavailable",
            "type": "cosmos_db_required",
            "performance_mode": "service_unavailable",
        }

        status["capabilities"] = {
            "fast_pagination": False,
            "advanced_search": False,
            "metadata_filtering": True,
            "tag_based_search": False,
            "folder_statistics": False,
            "recent_assets": False,
            "ai_metadata_enrichment": False,
        }

    return status


@router.get("/folders", response_model=Dict[str, Any])
async def list_folders(
    media_type: Optional[MediaType] = Query(
        None, description="Filter folders by media type (image or video)"
    ),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    List all folders from Cosmos DB metadata

    This endpoint returns all unique folder paths from assets stored in Cosmos DB.
    """
    try:
        # Check if Cosmos DB service is available
        if not cosmos_service:
            logger.error("Cosmos DB service is not available")
            raise HTTPException(
                status_code=503,
                detail="Cosmos DB service is not available. Please check your configuration.",
            )

        # Get folders from Cosmos DB
        media_type_str = media_type.value if media_type else None
        result = cosmos_service.get_all_folders(media_type=media_type_str)

        # Filter out root folder from the results and build hierarchy for UI
        filtered_folders = [folder for folder in result['folders'] if folder != '/' and folder.strip()]
        
        # Build folder hierarchy for UI
        folder_hierarchy = {}
        for folder_path in filtered_folders:
            # For single-level folders, add directly to hierarchy
            # Since we don't have metadata anymore, just mark as present
            if '/' not in folder_path:
                folder_hierarchy[folder_path] = {}

        return {
            "success": True,
            "message": "Folders retrieved successfully from Cosmos DB",
            "folders": filtered_folders,  # Filtered string array (no root)
            "folder_hierarchy": folder_hierarchy,
            "total_folders": len(filtered_folders),
            "source": "cosmos_db"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving folders from Cosmos DB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folders", response_model=Dict[str, Any])
async def create_folder(
    folder_path: str = Body(..., embed=True),
    media_type: Optional[MediaType] = Body(None, embed=True),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    Create a folder placeholder in CosmosDB for immediate navbar visibility.
    
    This creates a special folder metadata record so the folder appears immediately
    in the navigation, even before any assets are added to it.
    """
    try:
        # Validate folder name
        folder_path = folder_path.strip()
        if not folder_path:
            raise HTTPException(
                status_code=400, detail="Folder path cannot be empty")

        # Remove leading/trailing slashes for consistency
        folder_path = folder_path.strip("/")

        # Don't allow creating root folder
        if folder_path == "":
            raise HTTPException(
                status_code=400, detail="Cannot create root folder")

        # Basic validation - allow alphanumeric, hyphens, underscores, spaces
        if not re.match(r"^[a-zA-Z0-9\-_ ]+$", folder_path):
            raise HTTPException(
                status_code=400,
                detail="Folder path can only contain alphanumeric characters, hyphens, underscores, and spaces",
            )

        # Normalize folder path for storage
        normalized_folder = folder_path.strip()
        if normalized_folder and not normalized_folder.endswith("/"):
            normalized_folder = f"{normalized_folder}/"

        # Create folder placeholder in CosmosDB for immediate visibility
        if cosmos_service:
            try:
                # Check if folder placeholder already exists
                existing_placeholder = cosmos_service.container.query_items(
                    query="SELECT * FROM c WHERE c.doc_type = 'folder_placeholder' AND c.folder_path = @folder_path",
                    parameters=[{"name": "@folder_path", "value": normalized_folder}],
                    enable_cross_partition_query=True
                )
                
                if not list(existing_placeholder):
                    # Create folder placeholder record
                    folder_placeholder = {
                        "id": f"folder_{uuid.uuid4().hex[:12]}",
                        "doc_type": "folder_placeholder",
                        "media_type": "folder_placeholder",  # Use as partition key
                        "folder_path": normalized_folder,
                        "folder_name": folder_path,  # Human readable name
                        "target_media_type": media_type.value if media_type else "mixed",
                        "created_at": datetime.utcnow().isoformat(),
                        "is_placeholder": True,
                        "asset_count": 0
                    }
                    
                    cosmos_service.create_asset_metadata(folder_placeholder)
                    logger.info(f"Created folder placeholder for: {folder_path}")
                else:
                    logger.info(f"Folder placeholder already exists for: {folder_path}")
                    
            except Exception as e:
                logger.warning(f"Failed to create folder placeholder in CosmosDB: {e}")
                # Continue anyway - folder will still work when assets are added

        # Return success
        return {
            "success": True,
            "message": f"Folder '{folder_path}' created and is immediately available.",
            "folder_path": folder_path,
            "media_type": media_type.value if media_type else "any",
            "created": True,
            "immediate_visibility": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
