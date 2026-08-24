"""Public and persisted models for asynchronous image-generation jobs."""

from datetime import datetime
from enum import Enum
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.models.images import (
    ImagePipelineRequest,
    ImageSaveResponse,
    PipelineAction,
)


class ImageJobStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    SAVING = "saving"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


TERMINAL_IMAGE_JOB_STATUSES = {
    ImageJobStatus.COMPLETED,
    ImageJobStatus.FAILED,
    ImageJobStatus.CANCELLED,
    ImageJobStatus.PARTIAL,
}


class ImageJobOutputStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    SAVING = "saving"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImageJobAnalysisStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageJobOutput(BaseModel):
    """Ordered, progressively updated output slot for a multi-image job."""

    index: int = Field(ge=1, le=10)
    status: ImageJobOutputStatus = ImageJobOutputStatus.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    asset: dict[str, Any] | None = None
    error: str | None = None
    analysis_status: ImageJobAnalysisStatus = ImageJobAnalysisStatus.NOT_REQUESTED


ACTIVE_IMAGE_JOB_STATUSES = {
    ImageJobStatus.GENERATING,
    ImageJobStatus.SAVING,
    ImageJobStatus.ANALYZING,
}


class ImageJobCreateRequest(BaseModel):
    """A durable generation request accepted independently of worker capacity."""

    request: ImagePipelineRequest
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    client_request_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_async_generation(self) -> "ImageJobCreateRequest":
        if self.request.action != PipelineAction.GENERATE:
            raise ValueError(
                "Asynchronous jobs currently support image generation only"
            )
        if not 1 <= self.request.n <= 10:
            raise ValueError("request.n must be between 1 and 10")
        if not self.request.save_options.enabled:
            raise ValueError(
                "Asynchronous jobs must enable save_options so results remain durable"
            )
        if self.request.n > 1 and not self.request.save_options.save_all:
            raise ValueError("Multi-image jobs must enable save_options.save_all")
        serialized = json.dumps(
            self.request.model_dump(mode="json"),
            separators=(",", ":"),
        ).encode("utf-8")
        if len(serialized) > 128 * 1024:
            raise ValueError("The image job request must be 128 KiB or smaller")
        return self


class ImageJob(BaseModel):
    """Public job representation returned to the frontend."""

    id: str
    revision: int = Field(default=1, ge=1)
    client_request_id: str | None = None
    status: ImageJobStatus
    stage: str
    progress: int = Field(ge=0, le=100)
    prompt: str
    model: str
    size: str
    folder_path: str | None = None
    analysis_enabled: bool = False
    requested_images: int = Field(ge=1, le=10)
    completed_images: int = Field(default=0, ge=0)
    failed_images: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: ImageSaveResponse | None = None
    error: str | None = None
    cancel_requested: bool = False
    attempt: int = Field(default=0, ge=0)
    parent_job_id: str | None = None
    outputs: list[ImageJobOutput] = Field(default_factory=list)


class ImageJobListResponse(BaseModel):
    jobs: list[ImageJob]
    total: int


class ImageJobRecord(ImageJob):
    """Internal document persisted to Cosmos DB; never used as a response model."""

    model_config = ConfigDict(extra="allow")

    owner_id: str
    media_type: str
    doc_type: Literal["image_generation_job"] = "image_generation_job"
    pipeline_request: dict[str, Any]
    request_hash: str | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    delivery_count: int = Field(default=0, ge=0)
    dispatched_at: datetime | None = None
    ttl: int | None = Field(default=None, ge=1)
