"""Public and persisted contracts for multi-image storylines."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.models.images import (
    GPT_IMAGE_2_MODEL,
    validate_image_model,
    validate_image_options,
    validate_image_size,
)
from backend.models.storyline_planning import StorylineCreativeDirection


def build_storyline_image_prompt(
    direction: StorylineCreativeDirection,
    *,
    purpose: str,
    frame_prompt: str,
) -> str:
    """Render the standalone prompt shared by validation and orchestration."""

    return "\n\n".join(
        [
            "Create one frame from a coherent multi-image campaign.",
            f"Creative direction: {direction.summary}",
            f"Visual style: {direction.visual_style}",
            f"Tone: {direction.tone}",
            f"Palette: {', '.join(direction.palette)}",
            "Continuity rules:\n- " + "\n- ".join(direction.continuity_rules),
            f"Narrative purpose: {purpose}",
            f"Frame instruction: {frame_prompt}",
            (
                "Keep campaign copy separate from the image. Do not add captions, "
                "headlines, labels, or other typography unless the frame instruction "
                "explicitly asks for visible text."
            ),
        ]
    )


class StorylineStatus(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


TERMINAL_STORYLINE_STATUSES = {
    StorylineStatus.COMPLETED,
    StorylineStatus.PARTIAL,
    StorylineStatus.FAILED,
    StorylineStatus.CANCELLED,
}

ACTIVE_STORYLINE_STATUSES = {
    StorylineStatus.DRAFT,
    StorylineStatus.PLANNED,
    StorylineStatus.QUEUED,
    StorylineStatus.GENERATING,
    StorylineStatus.CANCEL_REQUESTED,
}


class StorylineFrameStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    GENERATING = "generating"
    SAVING = "saving"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StorylineCopyDepth(str, Enum):
    PUNCHY = "punchy"
    BALANCED = "balanced"
    DETAILED = "detailed"


class StorylineReference(BaseModel):
    """A durable image reference available to a future storyline runner."""

    model_config = ConfigDict(frozen=True)

    reference_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1)
    blob_name: str = Field(min_length=1, max_length=1024)
    url: str = Field(min_length=1, max_length=4096)
    container: str = Field(min_length=1, max_length=256)
    content_type: str = Field(min_length=1, max_length=128)
    original_filename: str = Field(min_length=1, max_length=512)
    order: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def validate_image_reference(self) -> "StorylineReference":
        if not self.content_type.lower().startswith("image/"):
            raise ValueError("Storyline references must use an image content type")
        return self


class StorylineSettings(BaseModel):
    """Shared creative and image-provider settings for every storyline lane."""

    prompt: str = Field(default="", max_length=32000)
    frame_count: int = Field(default=4, ge=2, le=10)
    models: tuple[str, ...] = Field(default=(GPT_IMAGE_2_MODEL,), min_length=1)
    channel: str = Field(default="social", min_length=1, max_length=128)
    copy_depth: StorylineCopyDepth = StorylineCopyDepth.BALANCED
    size: str = Field(default="1024x1024", min_length=1, max_length=32)
    quality: str = Field(default="high")
    background: str = Field(default="auto")
    output_format: str = Field(default="png")
    output_compression: int = Field(default=100, ge=0, le=100)
    input_fidelity: str = Field(default="high")
    review_plan_first: bool = False
    folder_path: str | None = Field(default=None, max_length=1024)
    analysis_enabled: bool = False

    @model_validator(mode="after")
    def validate_provider_settings(self) -> "StorylineSettings":
        if len(set(self.models)) != len(self.models):
            raise ValueError("Storyline models must be unique")
        if self.input_fidelity not in {"low", "high"}:
            raise ValueError("input_fidelity must be either 'low' or 'high'")
        for model in self.models:
            validate_image_model(model)
            validate_image_size(model, self.size)
            validate_image_options(
                model,
                quality=self.quality,
                output_format=self.output_format,
                response_format="b64_json",
                background=self.background,
            )
        return self


class StorylineFrameAsset(BaseModel):
    """Durable generated asset attached to a single lane frame."""

    model_config = ConfigDict(extra="allow", frozen=True)

    blob_name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    container: str | None = None
    content_type: str | None = None
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)


class StorylineFrame(BaseModel):
    """One executable frame within a model-specific lane."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    frame_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1)
    plan_frame_id: str = Field(min_length=1)
    lane_id: str = Field(min_length=1)
    order: int = Field(ge=1, le=10)
    title: str | None = Field(default=None, min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=1000)
    prompt: str = Field(min_length=1, max_length=32000)
    copy_text: str = Field(alias="copy", min_length=1, max_length=2000)
    status: StorylineFrameStatus = StorylineFrameStatus.PENDING
    attempt: int = Field(default=0, ge=0)
    asset: StorylineFrameAsset | None = None
    image_job_id: str | None = None
    error: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_state_payload(self) -> "StorylineFrame":
        if self.status == StorylineFrameStatus.READY and self.asset is None:
            raise ValueError("Ready storyline frames must include an asset")
        if self.status != StorylineFrameStatus.READY and self.asset is not None:
            raise ValueError("Only ready storyline frames may include an asset")
        if self.status == StorylineFrameStatus.FAILED and not self.error:
            raise ValueError("Failed storyline frames must include an error")
        return self


class StorylineLane(BaseModel):
    """A model-specific rendering lane for the shared logical frame plan."""

    model_config = ConfigDict(frozen=True)

    lane_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1)
    model: str = Field(min_length=1)
    label: str | None = Field(default=None, max_length=256)
    capability_disclosure: str | None = Field(default=None, max_length=2000)
    reference_image_limit: int = Field(default=10, ge=0, le=10)
    reduced_reference_fidelity: bool = False
    frames: tuple[StorylineFrame, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_frames(self) -> "StorylineLane":
        if any(frame.lane_id != self.lane_id for frame in self.frames):
            raise ValueError("Every frame lane_id must match its containing lane")
        orders = [frame.order for frame in self.frames]
        if orders != list(range(1, len(self.frames) + 1)):
            raise ValueError("Lane frame order must be contiguous and start at one")
        if len({frame.frame_id for frame in self.frames}) != len(self.frames):
            raise ValueError("Frame IDs must be unique within a lane")
        if len({frame.plan_frame_id for frame in self.frames}) != len(self.frames):
            raise ValueError("Plan frame IDs must be unique within a lane")
        return self


class StorylinePlan(BaseModel):
    """Immutable creative plan replaced atomically after user review."""

    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1)
    version: int = Field(default=1, ge=1)
    creative_direction: StorylineCreativeDirection
    lanes: tuple[StorylineLane, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_lane_alignment(self) -> "StorylinePlan":
        lane_ids = [lane.lane_id for lane in self.lanes]
        lane_models = [lane.model for lane in self.lanes]
        if len(set(lane_ids)) != len(lane_ids):
            raise ValueError("Storyline lane IDs must be unique")
        if len(set(lane_models)) != len(lane_models):
            raise ValueError("Storyline lanes must use unique models")

        frame_ids = [frame.frame_id for lane in self.lanes for frame in lane.frames]
        if len(set(frame_ids)) != len(frame_ids):
            raise ValueError("Storyline frame IDs must be globally unique")

        logical_frame_ids = tuple(
            frame.plan_frame_id for frame in self.lanes[0].frames
        )
        logical_content = tuple(
            (
                frame.order,
                frame.plan_frame_id,
                frame.title,
                frame.purpose,
                frame.prompt,
                frame.copy_text,
            )
            for frame in self.lanes[0].frames
        )
        for lane in self.lanes[1:]:
            if tuple(frame.plan_frame_id for frame in lane.frames) != logical_frame_ids:
                raise ValueError(
                    "Every model lane must share the same ordered plan frame IDs"
                )
            lane_content = tuple(
                (
                    frame.order,
                    frame.plan_frame_id,
                    frame.title,
                    frame.purpose,
                    frame.prompt,
                    frame.copy_text,
                )
                for frame in lane.frames
            )
            if lane_content != logical_content:
                raise ValueError(
                    "Every model lane must share identical ordered frame content"
                )
        for frame in self.lanes[0].frames:
            rendered = build_storyline_image_prompt(
                self.creative_direction,
                purpose=frame.purpose,
                frame_prompt=frame.prompt,
            )
            if len(rendered) > 32000:
                raise ValueError(
                    "The rendered image prompt for each storyline frame must be "
                    "32000 characters or fewer"
                )
        return self

    def validate_against(self, settings: StorylineSettings) -> None:
        if tuple(lane.model for lane in self.lanes) != settings.models:
            raise ValueError(
                "Storyline plan lanes must match settings.models in the same order"
            )
        for lane in self.lanes:
            if len(lane.frames) != settings.frame_count:
                raise ValueError(
                    "Every storyline lane must contain settings.frame_count frames"
                )


class StorylineCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    settings: StorylineSettings
    references: tuple[StorylineReference, ...] = Field(default=(), max_length=10)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    client_request_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_references(self) -> "StorylineCreateRequest":
        if not self.settings.prompt.strip() and not self.references:
            raise ValueError(
                "A storyline requires a text prompt, at least one image, or both"
            )
        ids = [reference.reference_id for reference in self.references]
        blobs = [reference.blob_name for reference in self.references]
        orders = [reference.order for reference in self.references]
        if len(set(ids)) != len(ids):
            raise ValueError("Storyline reference IDs must be unique")
        if len(set(blobs)) != len(blobs):
            raise ValueError("Storyline reference blobs must be unique")
        if orders != list(range(1, len(self.references) + 1)):
            raise ValueError("Storyline reference order must be contiguous and start at one")
        return self


class StorylineMutationRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)
    expected_etag: str | None = Field(default=None, min_length=1)


class StorylinePlanUpdateRequest(StorylineMutationRequest):
    plan: StorylinePlan


class StorylineFrameActionRequest(StorylineMutationRequest):
    model_config = ConfigDict(populate_by_name=True)

    reason: str | None = Field(default=None, max_length=1000)
    prompt: str | None = Field(default=None, min_length=1, max_length=32000)
    copy_text: str | None = Field(
        default=None,
        alias="copy",
        min_length=1,
        max_length=2000,
    )


class Storyline(BaseModel):
    """Public storyline aggregate returned by the API."""

    id: str
    revision: int = Field(default=1, ge=1)
    etag: str | None = None
    client_request_id: str | None = None
    status: StorylineStatus
    stage: str
    progress: int = Field(default=0, ge=0, le=100)
    title: str
    settings: StorylineSettings
    references: tuple[StorylineReference, ...] = ()
    plan: StorylinePlan | None = None
    error: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_plan_settings(self) -> "Storyline":
        if self.plan is not None:
            self.plan.validate_against(self.settings)
        return self


class StorylineListResponse(BaseModel):
    items: list["StorylineSummary"]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class StorylineSummary(BaseModel):
    """Lightweight list item; full plans are fetched only for the selected story."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    revision: int = Field(ge=1)
    etag: str | None = None
    client_request_id: str | None = None
    status: StorylineStatus
    stage: str
    progress: int = Field(ge=0, le=100)
    title: str
    settings: "StorylineSettingsSummary"
    error: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class StorylineSettingsSummary(BaseModel):
    """Settings required to render the storyline list without the full brief."""

    model_config = ConfigDict(from_attributes=True)

    frame_count: int = Field(ge=2, le=10)
    models: tuple[str, ...] = Field(min_length=1)
    channel: str
    copy_depth: StorylineCopyDepth
    size: str
    review_plan_first: bool


class StorylineRecord(Storyline):
    """Internal Cosmos document; external callers receive ``Storyline``."""

    model_config = ConfigDict(extra="allow")

    owner_id: str
    media_type: Literal["storyline"] = "storyline"
    doc_type: Literal["storyline"] = "storyline"
    request_hash: str | None = None
    idempotency_key: str | None = None
    ttl: int | None = Field(default=None, ge=1)
