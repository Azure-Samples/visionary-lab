"""Mock-provider integration coverage for the Storyline orchestration boundary."""

import pytest

from backend.models.images import GPT_IMAGE_2_MODEL, PipelineAction
from backend.models.storylines import StorylineStatus
from tests.test_storyline_orchestrator import (
    OWNER_ID,
    REFERENCE_PREFIX,
    RecordingRunner,
    create_request,
    running_storyline_stack,
    wait_for_storyline,
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_text_storyline_reuses_one_saved_anchor_for_later_frames():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, _):
        created = await orchestrator.create(
            create_request(frame_count=3),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            created.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert completed.plan is not None
        anchor_blob = completed.plan.lanes[0].frames[0].asset.blob_name
        calls_by_order = {
            int(call.metadata["storyline_frame_index"]): call
            for call in runner.calls
        }
        assert calls_by_order[1].action == PipelineAction.GENERATE
        for order in (2, 3):
            call = calls_by_order[order]
            assert call.action == PipelineAction.EDIT
            assert [item.blob_name for item in call.source_image_blobs] == [
                anchor_blob
            ]


async def test_multi_reference_storyline_uses_durable_inputs_for_every_frame():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, _):
        created = await orchestrator.create(
            create_request(frame_count=2, reference_count=2),
            owner_id=OWNER_ID,
        )
        await wait_for_storyline(
            orchestrator,
            created.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert len(runner.calls) == 2
        for call in runner.calls:
            assert call.model == GPT_IMAGE_2_MODEL
            assert call.action == PipelineAction.EDIT
            assert call.source_image_urls is None
            assert call.source_image_base64 is None
            assert [item.blob_name for item in call.source_image_blobs] == [
                f"{REFERENCE_PREFIX}reference-1.png",
                f"{REFERENCE_PREFIX}reference-2.png",
            ]
