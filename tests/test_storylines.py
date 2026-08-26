"""Validation, persistence, and HTTP-contract tests for storylines."""

from __future__ import annotations

import io

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image
from pydantic import ValidationError

from backend.api.endpoints.storylines import (
    get_storyline_storage,
    router as storylines_router,
)
from backend.models.storyline_planning import StorylineCreativeDirection
from backend.models.storylines import (
    StorylineCreateRequest,
    StorylineFrame,
    StorylineFrameAsset,
    StorylineFrameStatus,
    StorylineLane,
    StorylinePlan,
    StorylineReference,
    StorylineRecord,
    StorylineSettings,
    StorylineStatus,
)
from backend.storylines.manager import StorylineConflictError, StorylineManager
from backend.storylines.orchestrator import StorylineOrchestrator
from backend.storylines.references import storyline_reference_prefix
from backend.storylines.store import CosmosStorylineStore, MemoryStorylineStore


_ONE_PIXEL_PNG_BUFFER = io.BytesIO()
Image.new("RGB", (1, 1), color="white").save(_ONE_PIXEL_PNG_BUFFER, format="PNG")
_ONE_PIXEL_PNG = _ONE_PIXEL_PNG_BUFFER.getvalue()


def creative_direction() -> StorylineCreativeDirection:
    return StorylineCreativeDirection(
        summary="A coherent launch story",
        visual_style="Editorial product photography with geometric staging",
        tone="Confident and optimistic",
        palette=["midnight blue", "electric cyan"],
        continuity_rules=["Keep the same hero product", "Use one lighting direction"],
    )


def frame(
    lane_id: str,
    order: int,
    *,
    status: StorylineFrameStatus = StorylineFrameStatus.PENDING,
) -> StorylineFrame:
    asset = (
        StorylineFrameAsset(
            blob_name=f"story/frame-{order}.png",
            url=f"https://storage.example/story/frame-{order}.png",
        )
        if status == StorylineFrameStatus.READY
        else None
    )
    return StorylineFrame(
        frame_id=f"{lane_id}-frame-{order}",
        plan_frame_id=f"beat-{order}",
        lane_id=lane_id,
        order=order,
        title=f"Frame {order}",
        purpose=f"Narrative purpose {order}",
        prompt=f"Render the shared subject in scene {order}",
        copy=f"Campaign copy {order}",
        status=status,
        asset=asset,
        error="provider rejected frame" if status == StorylineFrameStatus.FAILED else None,
    )


def with_status(
    value: StorylineFrame,
    status: StorylineFrameStatus,
) -> StorylineFrame:
    payload = value.model_dump(mode="python")
    payload.update(
        {
            "status": status,
            "asset": (
                StorylineFrameAsset(
                    blob_name=f"story/{value.frame_id}.png",
                    url=f"https://storage.example/story/{value.frame_id}.png",
                )
                if status == StorylineFrameStatus.READY
                else None
            ),
            "error": (
                "provider rejected frame"
                if status == StorylineFrameStatus.FAILED
                else None
            ),
        }
    )
    return StorylineFrame.model_validate(payload)


def plan(
    *,
    models: tuple[str, ...] = ("gpt-image-2",),
    frame_count: int = 2,
    first_status: StorylineFrameStatus = StorylineFrameStatus.PENDING,
    version: int = 1,
    plan_id: str = "plan-1",
) -> StorylinePlan:
    lanes = []
    for lane_index, model in enumerate(models, start=1):
        lane_id = f"lane-{lane_index}"
        lanes.append(
            StorylineLane(
                lane_id=lane_id,
                model=model,
                reference_image_limit=10 if model == "gpt-image-2" else 1,
                reduced_reference_fidelity=model != "gpt-image-2",
                frames=tuple(
                    frame(
                        lane_id,
                        order,
                        status=first_status
                        if order == 1
                        else StorylineFrameStatus.READY,
                    )
                    for order in range(1, frame_count + 1)
                ),
            )
        )
    return StorylinePlan(
        plan_id=plan_id,
        version=version,
        creative_direction=creative_direction(),
        lanes=tuple(lanes),
    )


def create_request(
    *,
    title: str = "Launch story",
    models: tuple[str, ...] = ("gpt-image-2",),
    frame_count: int = 2,
    idempotency_key: str | None = None,
) -> StorylineCreateRequest:
    return StorylineCreateRequest(
        title=title,
        settings=StorylineSettings(
            prompt="Introduce the product across a compact social campaign",
            frame_count=frame_count,
            models=models,
        ),
        references=(
            StorylineReference(
                reference_id="reference-1",
                blob_name="references/product.png",
                url="https://storage.example/references/product.png",
                container="images",
                content_type="image/png",
                original_filename="product.png",
                order=1,
            ),
        ),
        idempotency_key=idempotency_key,
    )


def test_storyline_defaults_are_immediate_four_frame_generation() -> None:
    settings = StorylineSettings(prompt="A four-beat product story")

    assert settings.frame_count == 4
    assert settings.review_plan_first is False
    assert settings.copy_depth.value == "balanced"
    assert settings.models == ("gpt-image-2",)


@pytest.mark.parametrize(
    ("ttl", "expected_ttl"),
    [
        (None, None),
        (3600, 3600),
    ],
)
def test_cosmos_storyline_document_omits_only_unset_ttl(
    ttl: int | None,
    expected_ttl: int | None,
) -> None:
    request = create_request()
    record = StorylineRecord(
        id="storyline-cosmos-document",
        status=StorylineStatus.DRAFT,
        stage=StorylineStatus.DRAFT.value,
        title=request.title,
        settings=request.settings,
        references=request.references,
        owner_id="owner-a",
        created_at="2026-08-26T10:30:00Z",
        updated_at="2026-08-26T10:30:00Z",
        ttl=ttl,
    )

    document = CosmosStorylineStore._document(record)

    if expected_ttl is None:
        assert "ttl" not in document
    else:
        assert document["ttl"] == expected_ttl
    assert "plan" in document
    assert document["plan"] is None


def test_storyline_rejects_duplicate_models_and_unordered_references() -> None:
    with pytest.raises(ValidationError, match="models must be unique"):
        StorylineSettings(
            prompt="Duplicate lane",
            models=("gpt-image-2", "gpt-image-2"),
        )

    reference = create_request().references[0]
    with pytest.raises(ValidationError, match="reference order"):
        StorylineCreateRequest(
            title="Bad references",
            settings=StorylineSettings(prompt="test"),
            references=(reference.model_copy(update={"order": 2}),),
        )


def test_storyline_accepts_image_only_input_but_rejects_empty_input() -> None:
    image_only = StorylineCreateRequest(
        title="Image-only story",
        settings=StorylineSettings(prompt=""),
        references=create_request().references,
    )
    assert image_only.settings.prompt == ""
    assert len(image_only.references) == 1

    with pytest.raises(ValidationError, match="text prompt, at least one image"):
        StorylineCreateRequest(
            title="Empty story",
            settings=StorylineSettings(prompt=""),
            references=(),
        )


def test_storyline_orchestrator_rejects_foreign_reference_coordinates() -> None:
    request = create_request().model_copy(
        update={
            "references": (
                create_request().references[0].model_copy(
                    update={"blob_name": "storyline-references/another-owner/image.png"}
                ),
            )
        }
    )

    with pytest.raises(StorylineConflictError, match="do not belong"):
        StorylineOrchestrator._validate_create_request(
            request,
            owner_id="owner-a",
        )

    owned = request.references[0].model_copy(
        update={
            "blob_name": f"{storyline_reference_prefix('owner-a')}image.png"
        }
    )
    owned_request = request.model_copy(update={"references": (owned,)})
    StorylineOrchestrator._validate_create_request(
        owned_request,
        owner_id="owner-a",
    )


def test_storyline_orchestrator_rejects_unconfigured_models(monkeypatch) -> None:
    from backend.core.config import settings

    monkeypatch.setattr(settings, "FLUX_KONTEXT_DEPLOYMENT", None)
    request = StorylineCreateRequest(
        title="Unavailable lane",
        settings=StorylineSettings(
            prompt="Compare providers",
            models=("flux-kontext-pro",),
        ),
    )

    with pytest.raises(StorylineConflictError, match="not configured"):
        StorylineOrchestrator._validate_create_request(
            request,
            owner_id="owner-a",
        )


def test_plan_requires_aligned_lane_frames_and_is_frozen() -> None:
    first_lane = StorylineLane(
        lane_id="lane-1",
        model="gpt-image-2",
        frames=(frame("lane-1", 1), frame("lane-1", 2)),
    )
    second_lane = StorylineLane(
        lane_id="lane-2",
        model="flux-kontext-pro",
        reference_image_limit=1,
        reduced_reference_fidelity=True,
        frames=(
            frame("lane-2", 1),
            frame("lane-2", 2).model_copy(update={"plan_frame_id": "other-beat"}),
        ),
    )

    with pytest.raises(ValidationError, match="same ordered plan frame IDs"):
        StorylinePlan(
            creative_direction=creative_direction(),
            lanes=(first_lane, second_lane),
        )

    valid_plan = plan()
    with pytest.raises(ValidationError, match="frozen"):
        valid_plan.version = 2


def test_plan_rejects_lane_specific_prompt_drift() -> None:
    shared = plan(models=("gpt-image-2", "flux-kontext-pro"))
    second_lane = shared.lanes[1]
    changed_frame = second_lane.frames[0].model_copy(
        update={"prompt": "A different prompt only for FLUX"}
    )

    with pytest.raises(ValidationError, match="identical ordered frame content"):
        StorylinePlan(
            plan_id=shared.plan_id,
            creative_direction=shared.creative_direction,
            lanes=(
                shared.lanes[0],
                second_lane.model_copy(
                    update={"frames": (changed_frame, *second_lane.frames[1:])}
                ),
            ),
        )


def test_plan_rejects_rendered_prompts_over_provider_limit() -> None:
    oversized = plan()
    first_lane = oversized.lanes[0]
    oversized_frame = first_lane.frames[0].model_copy(update={"prompt": "x" * 32000})

    with pytest.raises(ValidationError, match="rendered image prompt"):
        StorylinePlan(
            plan_id=oversized.plan_id,
            creative_direction=oversized.creative_direction,
            lanes=(
                first_lane.model_copy(
                    update={"frames": (oversized_frame, *first_lane.frames[1:])}
                ),
            ),
        )


@pytest.mark.asyncio
async def test_memory_persistence_scopes_owners_and_enforces_revision_etag() -> None:
    manager = StorylineManager(store=MemoryStorylineStore())
    await manager.start()
    try:
        first = await manager.create(
            create_request(idempotency_key="stable-create"), owner_id="owner-a"
        )
        duplicate = await manager.create(
            create_request(idempotency_key="stable-create"), owner_id="owner-a"
        )
        await manager.create(create_request(title="Other owner"), owner_id="owner-b")

        assert duplicate.id == first.id
        assert duplicate.etag == first.etag
        own_items, own_total = await manager.list_storylines(
            owner_id="owner-a", limit=50
        )
        assert own_total == 1
        assert [item.id for item in own_items] == [first.id]

        planned = await manager.update_plan(
            first.id,
            plan(),
            owner_id="owner-a",
            expected_revision=first.revision,
            expected_etag=first.etag,
        )
        assert planned.status == StorylineStatus.PLANNED
        assert planned.revision == first.revision + 1
        assert planned.etag != first.etag

        with pytest.raises(StorylineConflictError, match="revision"):
            await manager.update_plan(
                first.id,
                plan(version=2),
                owner_id="owner-a",
                expected_revision=first.revision,
            )

        active = await manager.store.list_active()
        assert {item.owner_id for item in active} == {"owner-a", "owner-b"}

        cancelled = await manager.cancel(planned.id, owner_id="owner-a")
        assert cancelled.status == StorylineStatus.CANCELLED
        active = await manager.store.list_active()
        assert len(active) == 1
        assert active[0].owner_id == "owner-b"
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_reviewed_plan_can_change_frame_count_within_product_limits() -> None:
    manager = StorylineManager(store=MemoryStorylineStore())
    await manager.start()
    try:
        created = await manager.create(
            create_request(frame_count=2),
            owner_id="owner-a",
        )

        updated = await manager.update_plan(
            created.id,
            plan(frame_count=3),
            owner_id="owner-a",
        )

        assert updated.settings.frame_count == 3
        assert len(updated.plan.lanes[0].frames) == 3
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_plan_updates_strip_client_supplied_execution_state() -> None:
    manager = StorylineManager(store=MemoryStorylineStore())
    await manager.start()
    try:
        created = await manager.create(create_request(), owner_id="owner-a")
        injected = plan(first_status=StorylineFrameStatus.READY)

        planned = await manager.update_plan(
            created.id,
            injected,
            owner_id="owner-a",
        )

        assert all(
            frame.status == StorylineFrameStatus.PENDING
            and frame.asset is None
            and frame.image_job_id is None
            and frame.attempt == 0
            for lane in planned.plan.lanes
            for frame in lane.frames
        )

        queued_record = await manager.mutate_record(
            planned.id,
            owner_id="owner-a",
            mutator=lambda record: record.model_copy(
                update={"status": StorylineStatus.QUEUED}
            ),
        )
        with pytest.raises(StorylineConflictError, match="before generation"):
            await manager.update_plan(
                planned.id,
                plan(version=2),
                owner_id="owner-a",
                expected_revision=queued_record.revision,
            )
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_frame_retry_and_regenerate_are_atomic_reset_operations() -> None:
    manager = StorylineManager(store=MemoryStorylineStore())
    await manager.start()
    try:
        created = await manager.create(create_request(), owner_id="owner-a")
        planned = await manager.update_plan(
            created.id,
            plan(first_status=StorylineFrameStatus.FAILED),
            owner_id="owner-a",
        )
        seeded = await manager.mutate_record(
            planned.id,
            owner_id="owner-a",
            mutator=lambda record: record.model_copy(
                update={
                    "plan": manager._map_frames(
                        record.plan,
                        lambda item: with_status(
                            item,
                            StorylineFrameStatus.FAILED
                            if item.frame_id == "lane-1-frame-1"
                            else StorylineFrameStatus.READY,
                        ),
                    )
                }
            ),
        )
        planned = manager.to_public(seeded)

        retried = await manager.retry_frame(
            planned.id,
            "lane-1-frame-1",
            owner_id="owner-a",
            expected_revision=planned.revision,
            prompt="Updated failed-frame prompt",
            copy_text="Updated campaign copy",
        )
        retried_frame = retried.plan.lanes[0].frames[0]
        assert retried.status == StorylineStatus.QUEUED
        assert retried_frame.status == StorylineFrameStatus.PENDING
        assert retried_frame.attempt == 1
        assert retried_frame.prompt == "Updated failed-frame prompt"
        assert retried_frame.copy_text == "Updated campaign copy"
        assert retried_frame.error is None

        regenerated = await manager.regenerate_frame(
            retried.id,
            "lane-1-frame-2",
            owner_id="owner-a",
            expected_revision=retried.revision,
        )
        regenerated_frame = regenerated.plan.lanes[0].frames[1]
        assert regenerated_frame.status == StorylineFrameStatus.PENDING
        assert regenerated_frame.attempt == 1
        assert regenerated_frame.asset is None
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_regeneration_keeps_shared_plan_content_aligned_across_lanes() -> None:
    manager = StorylineManager(store=MemoryStorylineStore())
    await manager.start()
    try:
        created = await manager.create(
            create_request(models=("gpt-image-2", "flux-kontext-pro")),
            owner_id="owner-a",
        )
        planned = await manager.update_plan(
            created.id,
            plan(models=("gpt-image-2", "flux-kontext-pro")),
            owner_id="owner-a",
        )
        seeded = await manager.mutate_record(
            planned.id,
            owner_id="owner-a",
            mutator=lambda record: record.model_copy(
                update={
                    "plan": manager._map_frames(
                        record.plan,
                        lambda item: with_status(
                            item,
                            StorylineFrameStatus.READY,
                        ),
                    )
                }
            ),
        )
        planned = manager.to_public(seeded)

        regenerated = await manager.regenerate_frame(
            planned.id,
            "lane-1-frame-2",
            owner_id="owner-a",
            prompt="Shared revised prompt",
            copy_text="Shared revised copy",
        )

        logical_frames = [lane.frames[1] for lane in regenerated.plan.lanes]
        assert {frame.prompt for frame in logical_frames} == {"Shared revised prompt"}
        assert {frame.copy_text for frame in logical_frames} == {"Shared revised copy"}
        assert logical_frames[0].status == StorylineFrameStatus.PENDING
        assert logical_frames[1].status == StorylineFrameStatus.PENDING
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_storyline_http_create_list_get_and_owner_scope() -> None:
    manager = StorylineManager(store=MemoryStorylineStore())
    app = FastAPI()
    app.state.storyline_manager = manager
    app.include_router(storylines_router, prefix="/api/v1/storylines")
    await manager.start()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://api.example.test"
        ) as client:
            unauthenticated = await client.post(
                "/api/v1/storylines",
                json=create_request().model_dump(mode="json", by_alias=True),
            )
            assert unauthenticated.status_code == 401

            created_response = await client.post(
                "/api/v1/storylines",
                headers={"X-Image-Job-Owner": "browser-a"},
                json=create_request().model_dump(mode="json", by_alias=True),
            )
            assert created_response.status_code == 201
            created = created_response.json()
            assert created["status"] == "draft"
            assert created["plan"] is None

            listed = await client.get(
                "/api/v1/storylines",
                headers={"X-Image-Job-Owner": "browser-a"},
            )
            assert listed.status_code == 200
            assert listed.json()["total"] == 1
            assert "plan" not in listed.json()["items"][0]
            assert "references" not in listed.json()["items"][0]
            assert "prompt" not in listed.json()["items"][0]["settings"]

            hidden = await client.get(
                f"/api/v1/storylines/{created['id']}",
                headers={"X-Image-Job-Owner": "browser-b"},
            )
            assert hidden.status_code == 404
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_storyline_reference_upload_is_owner_scoped_and_durable() -> None:
    class FakeStorage:
        def __init__(self) -> None:
            self.folder_path = ""

        async def upload_asset(self, file, metadata=None, folder_path=None):
            del metadata
            self.folder_path = folder_path
            return {
                "file_id": file.filename.rsplit(".", 1)[0],
                "blob_name": f"{folder_path}{file.filename}",
                "url": f"https://storage.example/{folder_path}{file.filename}",
                "container": "images",
                "content_type": "image/png",
                "original_filename": file.filename,
            }

    manager = StorylineManager(store=MemoryStorylineStore())
    storage = FakeStorage()
    app = FastAPI()
    app.state.storyline_manager = manager
    app.include_router(storylines_router, prefix="/api/v1/storylines")
    app.dependency_overrides[get_storyline_storage] = lambda: storage
    await manager.start()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="https://api.example.test",
        ) as client:
            response = await client.post(
                "/api/v1/storylines/references",
                headers={"X-Image-Job-Owner": "browser-a"},
                data={"order": "1"},
                files={"file": ("product.png", _ONE_PIXEL_PNG, "image/png")},
            )

        assert response.status_code == 201
        payload = response.json()
        assert payload["blob_name"].startswith("storyline-references/")
        assert payload["blob_name"].endswith(".png")
        assert payload["blob_name"].rsplit("/", 1)[-1] != "product.png"
        assert payload["original_filename"] == "product.png"
        assert payload["order"] == 1
        assert storage.folder_path.startswith("storyline-references/")
    finally:
        await manager.close()
