"""Validated contracts for planning a coherent multi-image storyline."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


StorylineCopyDepth = Literal["punchy", "balanced", "detailed"]


class StorylinePlanningRequest(BaseModel):
    """Inputs needed by the LLM planner before any images are generated."""

    prompt: str = Field(min_length=1, max_length=32_000)
    frame_count: int = Field(ge=2, le=10)
    channel: str = Field(min_length=1, max_length=100)
    copy_depth: StorylineCopyDepth = "balanced"
    reference_image_urls: list[HttpUrl] = Field(default_factory=list, max_length=10)

    @field_validator("prompt", "channel")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class StorylineCreativeDirection(BaseModel):
    """Shared visual rules that every planned frame must follow."""

    summary: str = Field(min_length=1, max_length=2_000)
    visual_style: str = Field(min_length=1, max_length=1_000)
    tone: str = Field(min_length=1, max_length=500)
    palette: list[str] = Field(min_length=1, max_length=8)
    continuity_rules: list[str] = Field(min_length=1, max_length=12)

    @field_validator("summary", "visual_style", "tone")
    @classmethod
    def strip_direction_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("palette", "continuity_rules")
    @classmethod
    def validate_nonempty_items(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("items must not be blank")
        if any(len(value) > 1000 for value in normalized):
            raise ValueError("palette and continuity-rule items must be 1000 characters or fewer")
        return normalized


class StorylineFramePlan(BaseModel):
    """One ordered frame in the planned campaign storyline."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    index: int = Field(ge=1, le=10)
    purpose: str = Field(min_length=1, max_length=1_000)
    prompt: str = Field(min_length=1, max_length=32_000)
    copy_text: str = Field(
        alias="copy",
        serialization_alias="copy",
        min_length=1,
        max_length=2_000,
    )

    @field_validator("purpose", "prompt", "copy_text")
    @classmethod
    def strip_frame_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class StorylinePlan(BaseModel):
    """A complete creative direction and its ordered, executable frames."""

    creative_direction: StorylineCreativeDirection
    frames: list[StorylineFramePlan] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def validate_ordered_frames(self) -> "StorylinePlan":
        expected = list(range(1, len(self.frames) + 1))
        actual = [frame.index for frame in self.frames]
        if actual != expected:
            raise ValueError(
                "frames must be ordered and indexed consecutively starting at 1"
            )
        return self
