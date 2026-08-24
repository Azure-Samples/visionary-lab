from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

from backend.models.common import BaseResponse


class AssetMetadata(BaseModel):
    """Asset metadata model for Cosmos DB storage"""

    id: str = Field(..., description="Unique asset identifier")
    media_type: Literal["image"] = Field(
        ..., description="Asset type used as the partition key"
    )
    blob_name: str = Field(..., description="Blob name in Azure storage")
    container: str = Field(..., description="Storage container name")
    url: str = Field(..., description="URL to access the asset")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    content_type: Optional[str] = Field(None, description="MIME content type")
    folder_path: Optional[str] = Field("", description="Folder path in storage")

    # AI-generated content metadata
    prompt: Optional[str] = Field(None, description="Generation prompt")
    model: Optional[str] = Field(None, description="AI model used")

    # Analysis results
    summary: Optional[str] = Field(None, description="AI-generated summary")
    description: Optional[str] = Field(None, description="AI-generated description")
    products: Optional[str] = Field(None, description="Identified products/brands")
    tags: Optional[List[str]] = Field(None, description="Metadata tags")
    feedback: Optional[str] = Field(None, description="AI feedback")

    # Technical metadata
    quality: Optional[str] = Field(None, description="Generation quality setting")
    background: Optional[str] = Field(None, description="Background setting")
    output_format: Optional[str] = Field(None, description="Output format")
    has_transparency: Optional[bool] = Field(
        None, description="Has transparent background"
    )

    # Custom metadata
    custom_metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional custom metadata"
    )

    # Timestamps and system fields
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    doc_type: str = Field(
        default="asset_metadata", description="Document type for querying"
    )


class AssetMetadataCreateRequest(BaseModel):
    """Request model for creating asset metadata"""

    media_type: Literal["image"] = Field(..., description="Asset type")
    blob_name: str = Field(..., description="Blob name in Azure storage")
    container: str = Field(..., description="Storage container name")
    url: str = Field(..., description="URL to access the asset")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    content_type: Optional[str] = Field(None, description="MIME content type")
    folder_path: Optional[str] = Field("", description="Folder path in storage")

    # AI-generated content metadata
    prompt: Optional[str] = Field(None, description="Generation prompt")
    model: Optional[str] = Field(None, description="AI model used")

    # Analysis results
    summary: Optional[str] = Field(None, description="AI-generated summary")
    description: Optional[str] = Field(None, description="AI-generated description")
    products: Optional[str] = Field(None, description="Identified products/brands")
    tags: Optional[List[str]] = Field(None, description="Metadata tags")
    feedback: Optional[str] = Field(None, description="AI feedback")

    # Technical metadata
    quality: Optional[str] = Field(None, description="Generation quality setting")
    background: Optional[str] = Field(None, description="Background setting")
    output_format: Optional[str] = Field(None, description="Output format")
    has_transparency: Optional[bool] = Field(
        None, description="Has transparent background"
    )

    # Custom metadata
    custom_metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional custom metadata"
    )


class AssetMetadataUpdateRequest(BaseModel):
    """Request model for updating asset metadata"""

    summary: Optional[str] = Field(None, description="AI-generated summary")
    description: Optional[str] = Field(None, description="AI-generated description")
    products: Optional[str] = Field(None, description="Identified products/brands")
    tags: Optional[List[str]] = Field(None, description="Metadata tags")
    feedback: Optional[str] = Field(None, description="AI feedback")
    custom_metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional custom metadata"
    )
    # NEW: Support nested analysis structure updates and analysis flag
    analysis: Optional[Dict[str, Any]] = Field(
        None, description="Nested analysis results structure"
    )
    has_analysis: Optional[bool] = Field(
        None, description="Flag indicating if analysis is available"
    )


class AssetMetadataResponse(BaseResponse):
    """Response model for asset metadata operations"""

    metadata: AssetMetadata = Field(..., description="Asset metadata")


class AssetMetadataListResponse(BaseResponse):
    """Response model for listing asset metadata"""

    items: List[AssetMetadata] = Field(..., description="List of asset metadata")
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Offset for pagination")
    has_more: bool = Field(..., description="Whether there are more items")


class AssetSearchRequest(BaseModel):
    """Request model for searching assets"""

    search_term: str = Field(..., description="Text to search for")
    media_type: Optional[Literal["image"]] = Field(None, description="Filter by asset type")
    folder_path: Optional[str] = Field(None, description="Filter by folder path")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    limit: int = Field(50, description="Maximum number of results", ge=1, le=100)
    offset: int = Field(0, description="Number of results to skip", ge=0)
    order_by: str = Field("created_at", description="Field to order by")
    order_desc: bool = Field(True, description="Order in descending order")


class AssetSearchResponse(BaseResponse):
    """Response model for asset search"""

    items: List[AssetMetadata] = Field(..., description="Search results")
    total: int = Field(..., description="Total number of results")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Offset for pagination")
    has_more: bool = Field(..., description="Whether there are more results")
    search_term: str = Field(..., description="The search term used")


class FolderStatsResponse(BaseResponse):
    """Response model for folder statistics"""

    folder_stats: List[Dict[str, Any]] = Field(..., description="Folder statistics")
    total_folders: int = Field(..., description="Total number of folders")


class RecentAssetsResponse(BaseResponse):
    """Response model for recent assets"""

    items: List[AssetMetadata] = Field(..., description="Recent assets")
    limit: int = Field(..., description="Number of items requested")


class MetadataSyncRequest(BaseModel):
    """Request model for syncing blob storage with Cosmos DB"""

    media_type: Optional[Literal["image"]] = Field(None, description="Asset type to sync")
    force_update: bool = Field(False, description="Force update existing metadata")
    batch_size: int = Field(100, description="Batch size for processing", ge=1, le=1000)


class MetadataSyncResponse(BaseResponse):
    """Response model for metadata sync operation"""

    processed: int = Field(..., description="Number of items processed")
    created: int = Field(..., description="Number of new metadata records created")
    updated: int = Field(..., description="Number of existing records updated")
    errors: int = Field(..., description="Number of errors encountered")
    details: List[str] = Field(..., description="Detailed processing information")
