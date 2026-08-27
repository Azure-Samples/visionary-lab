import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from backend.core.storyline_planner import (
    StorylinePlanner,
    StorylinePlanningError,
    UnavailableStorylinePlanner,
)
from backend.models.storyline_planning import StorylinePlanningRequest


def _plan_payload(frame_count: int = 3) -> dict:
    return {
        "creative_direction": {
            "summary": "A product journey from discovery to action.",
            "visual_style": "Cinematic studio photography with soft side light.",
            "tone": "Confident and optimistic.",
            "palette": ["cobalt blue", "warm white"],
            "continuity_rules": [
                "Keep the same cobalt bottle in every frame.",
                "Use the same soft side-light direction.",
            ],
        },
        "frames": [
            {
                "index": index,
                "purpose": f"Narrative beat {index}",
                "prompt": f"Standalone image prompt for frame {index}",
                "copy": f"Campaign copy {index}",
            }
            for index in range(1, frame_count + 1)
        ],
    }


def _response(payload: dict | str):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


@pytest.mark.asyncio
async def test_planner_sends_multimodal_references_and_returns_validated_plan():
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_response(_plan_payload()))
    planner = StorylinePlanner(client, "gpt-4o")
    request = StorylinePlanningRequest(
        prompt="Launch a premium refillable water bottle.",
        frame_count=3,
        channel="Instagram carousel",
        copy_depth="punchy",
        reference_image_urls=[
            "https://assets.example.test/bottle.png",
            "https://assets.example.test/brand-board.jpg",
        ],
    )

    plan = await planner.plan(request)

    assert len(plan.frames) == 3
    assert [frame.index for frame in plan.frames] == [1, 2, 3]
    assert plan.frames[0].copy_text == "Campaign copy 1"
    assert plan.model_dump()["frames"][0]["copy"] == "Campaign copy 1"
    assert plan.creative_direction.palette == ["cobalt blue", "warm white"]

    call = client.chat.completions.create.await_args.kwargs
    assert call["model"] == "gpt-4o"
    assert call["response_format"] == {"type": "json_object"}
    assert call["temperature"] == 0

    user_content = call["messages"][1]["content"]
    assert user_content[0]["type"] == "text"
    assert "CHANNEL: Instagram carousel" in user_content[0]["text"]
    assert "FRAME COUNT: 3" in user_content[0]["text"]
    assert "COPY DEPTH: punchy" in user_content[0]["text"]
    assert [item["image_url"]["url"] for item in user_content[1:]] == [
        "https://assets.example.test/bottle.png",
        "https://assets.example.test/brand-board.jpg",
    ]
    assert all(item["image_url"]["detail"] == "high" for item in user_content[1:])


@pytest.mark.asyncio
async def test_planner_retries_when_model_returns_wrong_frame_count():
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=[
            _response(_plan_payload(frame_count=2)),
            _response(_plan_payload(frame_count=3)),
        ]
    )
    planner = StorylinePlanner(client, "gpt-4o", max_attempts=2)

    plan = await planner.plan(
        StorylinePlanningRequest(
            prompt="Tell a three-part product story",
            frame_count=3,
            channel="LinkedIn",
            copy_depth="balanced",
        )
    )

    assert len(plan.frames) == 3
    assert client.chat.completions.create.await_count == 2
    retry_messages = client.chat.completions.create.await_args.kwargs["messages"]
    assert "exactly 3 ordered frames" in retry_messages[-1]["content"]


@pytest.mark.asyncio
async def test_planner_rejects_invalid_model_output_after_last_attempt():
    client = MagicMock()
    invalid = _plan_payload()
    invalid["frames"][1]["index"] = 1
    client.chat.completions.create = AsyncMock(return_value=_response(invalid))
    planner = StorylinePlanner(client, "gpt-4o", max_attempts=1)

    with pytest.raises(StorylinePlanningError, match="did not return a valid storyline"):
        await planner.plan(
            StorylinePlanningRequest(
                prompt="A coherent launch",
                frame_count=3,
                channel="Social",
                copy_depth="detailed",
            )
        )


def test_planning_request_enforces_product_copy_depth_values():
    with pytest.raises(ValidationError, match="copy_depth"):
        StorylinePlanningRequest(
            prompt="Campaign",
            frame_count=3,
            channel="Social",
            copy_depth="short",
        )


def test_planning_request_strips_required_text():
    request = StorylinePlanningRequest(
        prompt="  Campaign brief  ",
        frame_count=2,
        channel="  Email  ",
        copy_depth="balanced",
    )

    assert request.prompt == "Campaign brief"
    assert request.channel == "Email"


def test_creative_direction_bounds_individual_list_items():
    payload = _plan_payload(frame_count=2)
    payload["creative_direction"]["continuity_rules"] = ["x" * 1001]

    with pytest.raises(ValidationError, match="1000 characters or fewer"):
        from backend.models.storyline_planning import StorylinePlan

        StorylinePlan.model_validate(payload)


@pytest.mark.asyncio
async def test_unavailable_planner_fails_only_when_storyline_planning_is_requested():
    planner = UnavailableStorylinePlanner()

    with pytest.raises(StorylinePlanningError, match="LLM_DEPLOYMENT"):
        await planner.plan(
            StorylinePlanningRequest(
                prompt="Campaign",
                frame_count=2,
                channel="General",
            )
        )
