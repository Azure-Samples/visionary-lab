from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from models.common import BaseResponse


class MediaType(str, Enum):
    """Media type enumeration"""
    IMAGE = "image"
    VIDEO = "video"


class GalleryItem(BaseModel):
    """Gallery item model for both images and videos"""
    id: str = Field(..., description="Unique ID of the asset")
    name: str = Field(..., description="Name/filename of the asset")
    media_type: MediaType = Field(...,
                                  description="Type of media (image or video)")
    url: str = Field(..., description="URL to access the asset")
    container: str = Field(..., description="Storage container name")
    size: int = Field(..., description="Size of the asset in bytes")
    content_type: Optional[str] = Field(
        None, description="Content type of the asset")
    creation_time: Optional[str] = Field(
        None, description="Creation timestamp of the asset")
    last_modified: Optional[str] = Field(
        None, description="Last modified timestamp of the asset")
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Metadata associated with the asset")
    folder_path: Optional[str] = Field(
        "", description="Folder path where the asset is stored")

    # Computed properties
    @property
    def thumbnail_url(self) -> Optional[str]:
        """Get thumbnail URL (same as URL for now)"""
        return self.url


class GalleryResponse(BaseResponse):
    """Response model for gallery requests"""
    items: List[GalleryItem] = Field(..., description="List of gallery items")
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Offset for pagination")
    continuation_token: Optional[str] = Field(
        None, description="Token for next page of results")
    folders: Optional[List[str]] = Field(
        None, description="List of folder paths in the current view")


# Asset operation models
class AssetUploadResponse(BaseResponse):
    """Response model for asset upload operations"""
    file_id: str = Field(..., description="Unique ID of the uploaded asset")
    blob_name: str = Field(..., description="Blob name in storage")
    container: str = Field(..., description="Storage container name")
    url: str = Field(..., description="URL to access the asset")
    size: int = Field(..., description="Size of the asset in bytes")
    content_type: str = Field(..., description="Content type of the asset")
    original_filename: str = Field(..., description="Original filename")
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Metadata associated with the asset")
    folder_path: Optional[str] = Field(
        "", description="Folder path where the asset is stored")


class AssetDeleteResponse(BaseResponse):
    """Response model for asset deletion operations"""
    blob_name: str = Field(..., description="Name of the deleted blob")
    container: str = Field(..., description="Container of the deleted blob")


class AssetUrlResponse(BaseResponse):
    """Response model for asset URL retrieval"""
    url: str = Field(..., description="URL to access the asset")
    blob_name: str = Field(..., description="Blob name in storage")
    container: str = Field(..., description="Storage container name")


class AssetMetadataResponse(BaseResponse):
    """Response model for asset metadata operations"""
    blob_name: str = Field(..., description="Blob name in storage")
    container: str = Field(..., description="Storage container name")
    metadata: Dict[str, str] = Field(...,
                                     description="Metadata associated with the asset")


class MetadataUpdateRequest(BaseModel):
    """Request model for updating asset metadata"""
    metadata: Dict[str, Any] = Field(...,
                                     description="Metadata to apply to the asset")


class SasTokenResponse(BaseModel):
    """Response model for SAS token generation endpoint"""
    success: bool
    message: str
    image_sas_token: str
    image_container_url: str
    expiry: datetime
