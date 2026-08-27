"""LLM-backed planning for coherent, ordered image storylines."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from backend.models.storyline_planning import StorylinePlan, StorylinePlanningRequest


_COPY_DEPTH_GUIDANCE = {
    "punchy": "Write compact, high-impact copy, usually a short hook or CTA.",
    "balanced": "Write concise campaign copy with one clear idea per frame.",
    "detailed": "Write fuller campaign copy with enough context to stand alone.",
}


_STORYLINE_PLANNER_SYSTEM_MESSAGE = """You are a creative director planning a coherent multi-image campaign.

Create one shared creative direction, then a deliberately ordered sequence of frames. The frames are not variants of one prompt: each frame must have a distinct narrative purpose while remaining recognizably part of the same campaign.

When reference images are supplied, treat them as factual visual anchors. Preserve the important subjects, products, identity cues, materials, and brand details visible in them. State the reusable visual anchors as continuity rules, and repeat the necessary anchors in every standalone image-generation prompt.

Each frame prompt must be directly usable by an image model without relying on hidden conversation context. Keep campaign copy separate from the image prompt; do not ask the image model to render the copy unless the user's brief explicitly asks for visible text in the image.

Return only a valid JSON object with this exact shape:
{
  "creative_direction": {
    "summary": "shared campaign concept",
    "visual_style": "medium, composition, lighting, lens or rendering treatment",
    "tone": "emotional tone",
    "palette": ["specific color or material direction"],
    "continuity_rules": ["specific rule repeated across every frame"]
  },
  "frames": [
    {
      "index": 1,
      "purpose": "the frame's role in the narrative",
      "prompt": "a standalone image-generation prompt",
      "copy": "editable channel-ready campaign copy"
    }
  ]
}

Use exactly the requested number of frames, indexed consecutively from 1. Every string and every list must be non-empty.
"""


class StorylinePlanningError(RuntimeError):
    """Raised when the planning model does not return a usable plan."""


class UnavailableStorylinePlanner:
    """Keep existing image workflows online when the LLM is not configured."""

    async def plan(self, request: StorylinePlanningRequest) -> StorylinePlan:
        del request
        raise StorylinePlanningError(
            "Storyline planning requires the LLM_DEPLOYMENT setting"
        )


class StorylinePlanner:
    """Plan storylines with an injected async OpenAI-compatible LLM client."""

    def __init__(self, async_llm_client: Any, model: str, *, max_attempts: int = 2):
        if not model or not model.strip():
            raise ValueError("A planning model deployment is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.client = async_llm_client
        self.model = model.strip()
        self.max_attempts = max_attempts

    async def plan(self, request: StorylinePlanningRequest) -> StorylinePlan:
        """Return a validated creative direction and exact ordered frame plan."""

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _STORYLINE_PLANNER_SYSTEM_MESSAGE},
            {"role": "user", "content": self._user_content(request)},
        ]
        last_error: Exception | None = None

        for attempt in range(self.max_attempts):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw_content = self._response_content(response)
            try:
                payload = json.loads(raw_content)
                plan = StorylinePlan.model_validate(payload)
                self._validate_for_request(plan, request)
                return plan
            except (json.JSONDecodeError, TypeError, ValidationError, ValueError) as exc:
                last_error = exc
                if attempt + 1 >= self.max_attempts:
                    break
                messages.extend(
                    [
                        {"role": "assistant", "content": raw_content},
                        {
                            "role": "user",
                            "content": (
                                "Correct the JSON so it follows the required schema and "
                                f"contains exactly {request.frame_count} ordered frames. "
                                f"Validation error: {exc}"
                            ),
                        },
                    ]
                )

        raise StorylinePlanningError(
            f"The planning model did not return a valid storyline: {last_error}"
        ) from last_error

    @staticmethod
    def _user_content(request: StorylinePlanningRequest) -> list[dict[str, Any]]:
        copy_depth = request.copy_depth
        brief = "\n".join(
            [
                f"CHANNEL: {request.channel}",
                f"FRAME COUNT: {request.frame_count}",
                f"COPY DEPTH: {copy_depth}",
                f"COPY GUIDANCE: {_COPY_DEPTH_GUIDANCE[copy_depth]}",
                f"REFERENCE IMAGE COUNT: {len(request.reference_image_urls)}",
                "CAMPAIGN BRIEF:",
                request.prompt,
            ]
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": brief}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": str(url), "detail": "high"},
            }
            for url in request.reference_image_urls
        )
        return content

    @staticmethod
    def _response_content(response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise StorylinePlanningError(
                "The planning model returned an empty response"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise StorylinePlanningError(
                "The planning model returned an empty response"
            )
        return content

    @staticmethod
    def _validate_for_request(
        plan: StorylinePlan, request: StorylinePlanningRequest
    ) -> None:
        if len(plan.frames) != request.frame_count:
            raise ValueError(
                f"expected {request.frame_count} frames, received {len(plan.frames)}"
            )
