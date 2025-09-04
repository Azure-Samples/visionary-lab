from fastapi import APIRouter, HTTPException, Depends, Query, Body, BackgroundTasks
from typing import Dict, List, Optional, Any
import logging

from backend.core.cosmos_client import CosmosDBService
from backend.core.azure_storage import AzureBlobStorageService
from backend.core.config import settings
from backend.models.metadata_models import (
    AssetMetadata,
    AssetMetadataCreateRequest,
    AssetMetadataUpdateRequest,
    AssetMetadataResponse,
    AssetMetadataListResponse,
    AssetSearchRequest,
    AssetSearchResponse,
    FolderStatsResponse,
    RecentAssetsResponse,
    MetadataSyncRequest,
    MetadataSyncResponse,
)
from backend.models.gallery import MediaType

logger = logging.getLogger(__name__)
router = APIRouter()


def get_cosmos_service() -> CosmosDBService:
    """Dependency to get Cosmos DB service instance"""
    try:
        return CosmosDBService()
    except Exception as e:
        logger.error(f"Failed to initialize Cosmos DB service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Metadata service is currently unavailable. Please check your Cosmos DB configuration.",
        )


@router.post("/", response_model=AssetMetadataResponse)
async def create_asset_metadata(
    request: AssetMetadataCreateRequest,
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Create metadata record for an asset"""
    try:
        # Convert request to dict and create metadata
        asset_data = request.dict(exclude_unset=True)
        created_metadata = cosmos_service.create_asset_metadata(asset_data)

        return AssetMetadataResponse(
            success=True,
            message="Asset metadata created successfully",
            metadata=AssetMetadata(**created_metadata),
        )
    except Exception as e:
        logger.error(f"Error creating asset metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}", response_model=AssetMetadataResponse)
async def get_asset_metadata(
    asset_id: str,
    media_type: str = Query(..., description="Media type (partition key)"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Get metadata for a specific asset"""
    try:
        metadata = cosmos_service.get_asset_metadata(asset_id, media_type)
        if not metadata:
            raise HTTPException(
                status_code=404, detail="Asset metadata not found")

        return AssetMetadataResponse(
            success=True,
            message="Asset metadata retrieved successfully",
            metadata=AssetMetadata(**metadata),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting asset metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{asset_id}", response_model=AssetMetadataResponse)
async def update_asset_metadata(
    asset_id: str,
    media_type: str = Query(..., description="Media type (partition key)"),
    request: AssetMetadataUpdateRequest = Body(...),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Update metadata for an existing asset"""
    try:
        # Convert request to dict, excluding None values
        updates = request.dict(exclude_unset=True, exclude_none=True)

        if not updates:
            raise HTTPException(
                status_code=400, detail="No valid updates provided")

        updated_metadata = cosmos_service.update_asset_metadata(
            asset_id, media_type, updates
        )

        return AssetMetadataResponse(
            success=True,
            message="Asset metadata updated successfully",
            metadata=AssetMetadata(**updated_metadata),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating asset metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{asset_id}")
async def delete_asset_metadata(
    asset_id: str,
    media_type: str = Query(..., description="Media type (partition key)"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Delete metadata for an asset"""
    try:
        success = cosmos_service.delete_asset_metadata(asset_id, media_type)

        if not success:
            raise HTTPException(
                status_code=404, detail="Asset metadata not found")

        return {
            "success": True,
            "message": "Asset metadata deleted successfully",
            "asset_id": asset_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting asset metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=AssetMetadataListResponse)
async def list_asset_metadata(
    media_type: Optional[str] = Query(
        None, description="Filter by media type"),
    folder_path: Optional[str] = Query(
        None, description="Filter by folder path"),
    tags: Optional[str] = Query(
        None, description="Comma-separated tags to filter by"),
    limit: int = Query(
        50, description="Maximum number of results", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
    order_by: str = Query("created_at", description="Field to order by"),
    order_desc: bool = Query(True, description="Order in descending order"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """List asset metadata with filtering and pagination"""
    try:
        # Parse tags if provided
        tag_list = None
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        result = cosmos_service.query_assets(
            media_type=media_type,
            folder_path=folder_path,
            tags=tag_list,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_desc=order_desc,
        )

        # Convert items to AssetMetadata objects
        metadata_items = [AssetMetadata(**item) for item in result["items"]]

        return AssetMetadataListResponse(
            success=True,
            message="Asset metadata list retrieved successfully",
            items=metadata_items,
            total=result["total"],
            limit=limit,
            offset=offset,
            has_more=result["has_more"],
        )
    except Exception as e:
        logger.error(f"Error listing asset metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=AssetSearchResponse)
async def search_asset_metadata(
    request: AssetSearchRequest,
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Search asset metadata by text"""
    try:
        if request.search_term:
            # Use text search
            items = cosmos_service.search_assets(
                search_term=request.search_term,
                media_type=request.media_type,
                limit=request.limit,
            )
            total = len(items)
            has_more = False
        else:
            # Use advanced query with filters
            result = cosmos_service.query_assets(
                media_type=request.media_type,
                folder_path=request.folder_path,
                tags=request.tags,
                limit=request.limit,
                offset=request.offset,
                order_by=request.order_by,
                order_desc=request.order_desc,
            )
            items = result["items"]
            total = result["total"]
            has_more = result["has_more"]

        # Convert items to AssetMetadata objects
        metadata_items = [AssetMetadata(**item) for item in items]

        return AssetSearchResponse(
            success=True,
            message="Search completed successfully",
            items=metadata_items,
            total=total,
            limit=request.limit,
            offset=request.offset,
            has_more=has_more,
            search_term=request.search_term,
        )
    except Exception as e:
        logger.error(f"Error searching asset metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/folders", response_model=FolderStatsResponse)
async def get_folder_statistics(
    media_type: Optional[str] = Query(
        None, description="Filter by media type"),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Get folder usage statistics"""
    try:
        stats = cosmos_service.get_folder_stats(media_type=media_type)

        return FolderStatsResponse(
            success=True,
            message="Folder statistics retrieved successfully",
            folder_stats=stats["folder_stats"],
            total_folders=stats["total_folders"],
        )
    except Exception as e:
        logger.error(f"Error getting folder statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent", response_model=RecentAssetsResponse)
async def get_recent_assets(
    media_type: Optional[str] = Query(
        None, description="Filter by media type"),
    limit: int = Query(
        20, description="Maximum number of results", ge=1, le=100),
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
):
    """Get recently created assets"""
    try:
        items = cosmos_service.get_recent_assets(
            media_type=media_type, limit=limit)

        # Convert items to AssetMetadata objects
        metadata_items = [AssetMetadata(**item) for item in items]

        return RecentAssetsResponse(
            success=True,
            message="Recent assets retrieved successfully",
            items=metadata_items,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error getting recent assets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _sync_metadata_background(
    sync_request: MetadataSyncRequest,
    cosmos_service: CosmosDBService,
    azure_service: AzureBlobStorageService,
):
    """Background task to sync blob storage with Cosmos DB"""
    processed = 0
    created = 0
    updated = 0
    errors = 0
    details = []

    try:
        # Determine containers to sync
        containers = []
        if sync_request.media_type:
            if sync_request.media_type == "image":
                containers = [settings.AZURE_BLOB_IMAGE_CONTAINER]
            elif sync_request.media_type == "video":
                containers = [settings.AZURE_BLOB_VIDEO_CONTAINER]
        else:
            containers = [
                settings.AZURE_BLOB_IMAGE_CONTAINER,
                settings.AZURE_BLOB_VIDEO_CONTAINER,
            ]

        for container in containers:
            media_type = (
                "image" if container == settings.AZURE_BLOB_IMAGE_CONTAINER else "video"
            )
            details.append(f"Starting sync for {container} container")

            # List all blobs in the container
            continuation_token = None

            while True:
                blob_results = azure_service.list_blobs(
                    container_name=container,
                    limit=sync_request.batch_size,
                    marker=continuation_token,
                )

                blobs = blob_results["blobs"]
                if not blobs:
                    break

                for blob in blobs:
                    try:
                        processed += 1
                        blob_name = blob["name"]

                        # Skip folder markers
                        if blob_name.endswith(".folder"):
                            continue

                        # Extract asset ID from blob name
                        asset_id = blob_name.split(".")[0].split("/")[-1]

                        # Check if metadata already exists
                        existing_metadata = cosmos_service.get_asset_metadata(
                            asset_id, media_type
                        )

                        if existing_metadata and not sync_request.force_update:
                            # Skip if already exists and not forcing update
                            continue

                        # Create basic metadata object (no metadata extracted from blob storage)
                        metadata_dict = {
                            "id": asset_id,
                            "media_type": media_type,
                            "blob_name": blob_name,
                            "container": container,
                            "url": blob["url"],
                            "filename": blob_name.split("/")[-1],
                            "size": blob["size"],
                            "content_type": blob.get("content_type"),
                            "folder_path": blob.get("folder_path", ""),
                        }

                        # Note: Since we no longer store metadata in blob storage,
                        # sync only creates basic records with file information.
                        # Rich metadata (prompts, tags, etc.) should be added via API calls.

                        if existing_metadata:
                            # Update existing metadata
                            cosmos_service.update_asset_metadata(
                                asset_id, media_type, metadata_dict
                            )
                            updated += 1
                        else:
                            # Create new metadata
                            cosmos_service.create_asset_metadata(metadata_dict)
                            created += 1

                        # Log progress every 100 items
                        if processed % 100 == 0:
                            details.append(
                                f"Processed {processed} items in {container}"
                            )

                    except Exception as e:
                        errors += 1
                        logger.error(
                            f"Error syncing blob {blob.get('name', 'unknown')}: {e}"
                        )
                        continue

                # Check for continuation
                continuation_token = blob_results.get("continuation_token")
                if not continuation_token:
                    break

            details.append(
                f"Completed sync for {container}: {processed} processed")

    except Exception as e:
        logger.error(f"Error in metadata sync background task: {e}")
        details.append(f"Sync failed with error: {str(e)}")

    # Log final results
    logger.info(
        f"Metadata sync completed: {processed} processed, {created} created, {updated} updated, {errors} errors"
    )


@router.post("/sync", response_model=MetadataSyncResponse)
async def sync_metadata(
    background_tasks: BackgroundTasks,
    request: MetadataSyncRequest,
    cosmos_service: CosmosDBService = Depends(get_cosmos_service),
    azure_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()),
):
    """Sync blob storage metadata with Cosmos DB"""
    try:
        # Start background sync task
        background_tasks.add_task(
            _sync_metadata_background, request, cosmos_service, azure_service
        )

        return MetadataSyncResponse(
            success=True,
            message="Metadata sync started in background",
            processed=0,
            created=0,
            updated=0,
            errors=0,
            details=["Sync task started in background. Check logs for progress."],
        )
    except Exception as e:
        logger.error(f"Error starting metadata sync: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
