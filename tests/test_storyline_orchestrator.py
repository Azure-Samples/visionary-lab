"""Focused orchestration tests for durable multi-model storylines."""

from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import asynccontextmanager

import pytest

from backend.core.config import settings
from backend.jobs.manager import ImageJobManager, ImageJobProgress
from backend.jobs.queue import MemoryImageJobQueue
from backend.jobs.store import MemoryImageJobStore
from backend.models.image_jobs import ImageJobOutputStatus, ImageJobStatus
from backend.models.images import (
    FLUX_KONTEXT_PRO_MODEL,
    GPT_IMAGE_2_MODEL,
    ImagePipelineRequest,
    ImageSaveResponse,
    PipelineAction,
    SavedImageAsset,
)
from backend.models.storyline_planning import (
    StorylineCreativeDirection,
    StorylineFramePlan,
    StorylinePlan as PlannedStoryline,
    StorylinePlanningRequest,
)
from backend.models.storylines import (
    Storyline,
    StorylineCreateRequest,
    StorylineFrameStatus,
    StorylinePlan as PersistedStorylinePlan,
    StorylineReference,
    StorylineSettings,
    StorylineStatus,
)
from backend.storylines.manager import StorylineConflictError, StorylineManager
from backend.storylines.orchestrator import (
    RECONCILABLE_STORYLINE_STATUSES,
    StorylineOrchestrator,
)
from backend.storylines.references import storyline_reference_prefix
from backend.storylines.store import MemoryStorylineStore


OWNER_ID = "storyline-owner"
REFERENCE_PREFIX = storyline_reference_prefix(OWNER_ID)


class FakePlanner:
    def __init__(self) -> None:
        self.requests: list[StorylinePlanningRequest] = []

    async def plan(self, request: StorylinePlanningRequest) -> PlannedStoryline:
        self.requests.append(request)
        return planned_story(request)


def planned_story(request: StorylinePlanningRequest) -> PlannedStoryline:
    return PlannedStoryline(
        creative_direction=StorylineCreativeDirection(
            summary="One coherent product journey from discovery to action.",
            visual_style="Editorial studio photography with sculpted side light.",
            tone="Confident and optimistic.",
            palette=["cobalt blue", "warm white"],
            continuity_rules=[
                "Keep the same hero product in every frame.",
                "Keep the lighting direction and lens language stable.",
            ],
        ),
        frames=[
            StorylineFramePlan(
                index=index,
                purpose=f"Narrative beat {index}",
                prompt=f"Place the hero product in scene {index}",
                copy=f"Campaign copy {index}",
            )
            for index in range(1, request.frame_count + 1)
        ],
    )


class BarrierPlanner:
    """Hold two identical planning calls so their plan commits race."""

    def __init__(self) -> None:
        self.requests: list[StorylinePlanningRequest] = []
        self.both_started = asyncio.Event()
        self.release = asyncio.Event()

    async def plan(self, request: StorylinePlanningRequest) -> PlannedStoryline:
        self.requests.append(request)
        if len(self.requests) == 2:
            self.both_started.set()
        await self.release.wait()
        return planned_story(request)


class FailOncePlanner(FakePlanner):
    async def plan(self, request: StorylinePlanningRequest) -> PlannedStoryline:
        self.requests.append(request)
        if len(self.requests) == 1:
            raise RuntimeError("temporary planner failure")
        return planned_story(request)


class RecordingRunner:
    """Fake image runner with deterministic failure and blocking controls."""

    def __init__(
        self,
        *,
        blocked: set[tuple[str, int]] | None = None,
        fail_once: set[tuple[str, int]] | None = None,
    ) -> None:
        self.calls: list[ImagePipelineRequest] = []
        self.call_counts: Counter[tuple[str, int]] = Counter()
        self.blocked = blocked or set()
        self.fail_once = fail_once or set()
        self.started: dict[tuple[str, int], asyncio.Event] = {}
        self.releases: dict[tuple[str, int], asyncio.Event] = {}
        self.cancelled: set[tuple[str, int]] = set()

    def started_event(self, key: tuple[str, int]) -> asyncio.Event:
        return self.started.setdefault(key, asyncio.Event())

    def release(self, key: tuple[str, int]) -> None:
        self.releases.setdefault(key, asyncio.Event()).set()

    async def __call__(self, request, report_progress):
        request = request.model_copy(deep=True)
        metadata = request.metadata or {}
        frame_order = int(metadata["storyline_frame_index"])
        frame_id = str(metadata["storyline_frame_id"])
        key = (request.model, frame_order)
        self.calls.append(request)
        self.call_counts[key] += 1
        self.started_event(key).set()

        await report_progress(
            ImageJobProgress(
                status=ImageJobStatus.SAVING,
                progress=75,
                completed_images=0,
                failed_images=0,
                output_index=1,
                output_status=ImageJobOutputStatus.SAVING,
            )
        )

        if key in self.fail_once and self.call_counts[key] == 1:
            raise RuntimeError(f"provider rejected {request.model} frame {frame_order}")

        if key in self.blocked:
            try:
                await self.releases.setdefault(key, asyncio.Event()).wait()
            except asyncio.CancelledError:
                self.cancelled.add(key)
                raise

        attempt = self.call_counts[key]
        blob_name = f"storylines/{frame_id}-render-{attempt}.png"
        return ImageSaveResponse(
            success=True,
            message="saved",
            saved_images=[
                SavedImageAsset(
                    blob_name=blob_name,
                    url=f"https://assets.example.test/{blob_name}",
                    original_filename=blob_name.rsplit("/", 1)[-1],
                    original_index=1,
                    container="images",
                    content_type="image/png",
                    width=1024,
                    height=1024,
                )
            ],
            total_saved=1,
        )


def reference(order: int) -> StorylineReference:
    return StorylineReference(
        reference_id=f"reference-{order}",
        blob_name=f"{REFERENCE_PREFIX}reference-{order}.png",
        url=f"https://assets.example.test/reference-{order}.png",
        container="images",
        content_type="image/png",
        original_filename=f"reference-{order}.png",
        order=order,
    )


def create_request(
    *,
    frame_count: int = 3,
    models: tuple[str, ...] = (GPT_IMAGE_2_MODEL,),
    reference_count: int = 0,
    review_plan_first: bool = False,
) -> StorylineCreateRequest:
    return StorylineCreateRequest(
        title="Coherent launch storyline",
        settings=StorylineSettings(
            prompt="Launch the same hero product through an ordered social story.",
            frame_count=frame_count,
            models=models,
            channel="Instagram carousel",
            copy_depth="balanced",
            size="1024x1024",
            review_plan_first=review_plan_first,
        ),
        references=tuple(reference(index) for index in range(1, reference_count + 1)),
    )


@asynccontextmanager
async def running_storyline_stack(
    runner: RecordingRunner,
    *,
    concurrency: int = 10,
    planner=None,
):
    image_jobs = ImageJobManager(
        store=MemoryImageJobStore(),
        queue=MemoryImageJobQueue(),
        runner=runner,
        concurrency=concurrency,
        poll_interval=0.005,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
        heartbeat_interval=0.05,
        reconcile_interval=0.05,
        max_attempts=1,
    )
    planner = planner or FakePlanner()
    orchestrator = StorylineOrchestrator(
        manager=StorylineManager(store=MemoryStorylineStore()),
        image_jobs=image_jobs,
        planner=planner,  # type: ignore[arg-type]
        reconcile_interval=0.1,
        reference_url_builder=lambda item: _signed_reference_url(item),
    )
    await image_jobs.start()
    await orchestrator.start()
    try:
        yield orchestrator, image_jobs, planner
    finally:
        await orchestrator.close()
        await image_jobs.close()


async def _signed_reference_url(item: StorylineReference) -> str:
    return f"https://signed.example.test/{item.blob_name}?sig=test"


async def wait_for_storyline(
    orchestrator: StorylineOrchestrator,
    storyline_id: str,
    predicate,
    *,
    timeout: float = 5,
) -> Storyline:
    async with asyncio.timeout(timeout):
        while True:
            await orchestrator._reconcile_storyline(storyline_id)
            storyline = await orchestrator.get(storyline_id, owner_id=OWNER_ID)
            if predicate(storyline):
                return storyline
            await asyncio.sleep(0.01)


async def stop_storyline_reconciler(orchestrator: StorylineOrchestrator) -> None:
    reconciler, orchestrator._reconciler = orchestrator._reconciler, None
    if reconciler is not None:
        reconciler.cancel()
        await asyncio.gather(reconciler, return_exceptions=True)


def frames(storyline: Storyline):
    assert storyline.plan is not None
    return [frame for lane in storyline.plan.lanes for frame in lane.frames]


@pytest.mark.asyncio
async def test_immediate_text_only_story_uses_first_render_as_stable_lane_anchor():
    first_key = (GPT_IMAGE_2_MODEL, 1)
    runner = RecordingRunner(blocked={first_key})
    async with running_storyline_stack(runner) as (orchestrator, image_jobs, _):
        storyline = await orchestrator.create(create_request(), owner_id=OWNER_ID)
        await asyncio.wait_for(runner.started_event(first_key).wait(), timeout=1)

        assert storyline.status == StorylineStatus.GENERATING
        assert len(runner.calls) == 1
        assert runner.calls[0].action == PipelineAction.GENERATE
        assert runner.calls[0].source_image_blobs is None
        _, job_count = await image_jobs.list_jobs(owner_id=OWNER_ID, limit=20)
        assert job_count == 1

        runner.release(first_key)
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        calls_by_order = {
            int(call.metadata["storyline_frame_index"]): call for call in runner.calls
        }
        assert sorted(calls_by_order) == [1, 2, 3]
        anchor_asset = completed.plan.lanes[0].frames[0].asset
        assert anchor_asset is not None
        for order in (2, 3):
            request = calls_by_order[order]
            assert request.action == PipelineAction.EDIT
            assert request.source_image_blobs is not None
            assert len(request.source_image_blobs) == 1
            assert request.source_image_blobs[0].blob_name == anchor_asset.blob_name
            assert request.source_image_blobs[0].container == anchor_asset.container


@pytest.mark.asyncio
async def test_failed_text_anchor_is_terminal_and_exact_retry_unblocks_dependents():
    anchor_key = (GPT_IMAGE_2_MODEL, 1)
    runner = RecordingRunner(fail_once={anchor_key})
    async with running_storyline_stack(runner) as (orchestrator, _, _):
        storyline = await orchestrator.create(create_request(), owner_id=OWNER_ID)
        failed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.FAILED,
        )
        failed_frames = {frame.order: frame for frame in frames(failed)}
        assert failed.progress == 100
        assert failed_frames[1].status == StorylineFrameStatus.FAILED
        assert failed_frames[2].status == StorylineFrameStatus.PENDING
        assert failed_frames[3].status == StorylineFrameStatus.PENDING

        await orchestrator.retry_frame(
            storyline.id,
            failed_frames[1].frame_id,
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert runner.call_counts == Counter(
            {
                (GPT_IMAGE_2_MODEL, 1): 2,
                (GPT_IMAGE_2_MODEL, 2): 1,
                (GPT_IMAGE_2_MODEL, 3): 1,
            }
        )
        retried_anchor = completed.plan.lanes[0].frames[0]
        assert retried_anchor.attempt == 1
        assert retried_anchor.image_job_id != failed_frames[1].image_job_id
        assert all(
            frame.status == StorylineFrameStatus.READY for frame in frames(completed)
        )


@pytest.mark.asyncio
async def test_concurrent_idempotent_create_uses_committed_plan_winner():
    runner = RecordingRunner()
    planner = BarrierPlanner()
    async with running_storyline_stack(runner, planner=planner) as (
        orchestrator,
        _,
        _,
    ):
        request = create_request(review_plan_first=True).model_copy(
            update={"idempotency_key": "same-storyline-create"}
        )
        first = asyncio.create_task(orchestrator.create(request, owner_id=OWNER_ID))
        second = asyncio.create_task(orchestrator.create(request, owner_id=OWNER_ID))
        await asyncio.wait_for(planner.both_started.wait(), timeout=1)
        planner.release.set()
        first_result, second_result = await asyncio.gather(first, second)

        assert first_result.id == second_result.id
        assert first_result.plan is not None
        assert second_result.plan == first_result.plan
        persisted = await orchestrator.get(first_result.id, owner_id=OWNER_ID)
        assert persisted.status == StorylineStatus.PLANNED
        assert persisted.stage == StorylineStatus.PLANNED.value
        assert persisted.error is None
        assert persisted.plan == first_result.plan


@pytest.mark.asyncio
async def test_immediate_idempotent_replay_resumes_after_plan_commit_crash_window():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, planner):
        request = create_request(frame_count=2, reference_count=1).model_copy(
            update={"idempotency_key": "resume-after-plan-commit"}
        )
        created = await orchestrator.manager.create(request, owner_id=OWNER_ID)
        planning_request = StorylinePlanningRequest(
            prompt=created.settings.prompt,
            frame_count=created.settings.frame_count,
            channel=created.settings.channel,
            copy_depth=created.settings.copy_depth.value,
        )
        await orchestrator.manager.update_plan(
            created.id,
            orchestrator._materialize_plan(created, planned_story(planning_request)),
            owner_id=OWNER_ID,
        )

        resumed = await orchestrator.create(request, owner_id=OWNER_ID)
        completed = await wait_for_storyline(
            orchestrator,
            resumed.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert completed.id == created.id
        assert len(runner.calls) == 2
        assert planner.requests == []


@pytest.mark.asyncio
async def test_idempotent_replay_can_recover_a_planning_failure():
    runner = RecordingRunner()
    planner = FailOncePlanner()
    async with running_storyline_stack(runner, planner=planner) as (
        orchestrator,
        _,
        _,
    ):
        request = create_request(review_plan_first=True).model_copy(
            update={"idempotency_key": "recover-planner-failure"}
        )
        with pytest.raises(RuntimeError, match="temporary planner failure"):
            await orchestrator.create(request, owner_id=OWNER_ID)

        failed_items, total = await orchestrator.list_storylines(
            owner_id=OWNER_ID,
            limit=10,
        )
        assert total == 1
        assert failed_items[0].status == StorylineStatus.FAILED
        assert failed_items[0].stage == "planning_failed"
        assert failed_items[0].plan is None

        recovered = await orchestrator.create(request, owner_id=OWNER_ID)
        assert recovered.id == failed_items[0].id
        assert recovered.status == StorylineStatus.PLANNED
        assert recovered.plan is not None
        assert recovered.error is None


@pytest.mark.asyncio
async def test_retry_planning_keeps_review_first_draft_planned():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, planner):
        created = await orchestrator.manager.create(
            create_request(review_plan_first=True),
            owner_id=OWNER_ID,
        )

        planned = await orchestrator.retry_planning(
            created.id,
            owner_id=OWNER_ID,
            expected_revision=created.revision,
        )

        assert planned.status == StorylineStatus.PLANNED
        assert planned.plan is not None
        assert len(planner.requests) == 1
        assert runner.calls == []


@pytest.mark.asyncio
async def test_retry_planning_starts_immediate_draft_generation():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, planner):
        created = await orchestrator.manager.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )

        started = await orchestrator.retry_planning(
            created.id,
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            started.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert completed.plan is not None
        assert len(planner.requests) == 1
        assert len(runner.calls) == 2


@pytest.mark.asyncio
async def test_retry_planning_recovers_persisted_planning_failure():
    runner = RecordingRunner()
    planner = FailOncePlanner()
    async with running_storyline_stack(runner, planner=planner) as (
        orchestrator,
        _,
        _,
    ):
        created = await orchestrator.manager.create(
            create_request(review_plan_first=True),
            owner_id=OWNER_ID,
        )
        with pytest.raises(RuntimeError, match="temporary planner failure"):
            await orchestrator.retry_planning(created.id, owner_id=OWNER_ID)
        failed = await orchestrator.get(created.id, owner_id=OWNER_ID)
        assert failed.status == StorylineStatus.FAILED
        assert failed.stage == "planning_failed"

        recovered = await orchestrator.retry_planning(
            created.id,
            owner_id=OWNER_ID,
            expected_revision=failed.revision,
        )
        assert recovered.status == StorylineStatus.PLANNED
        assert recovered.plan is not None
        assert recovered.error is None
        assert len(planner.requests) == 2


@pytest.mark.asyncio
async def test_reviewed_plan_rejects_fewer_than_two_frames():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, _):
        created = await orchestrator.manager.create(
            create_request(review_plan_first=True),
            owner_id=OWNER_ID,
        )
        planning_request = StorylinePlanningRequest(
            prompt=created.settings.prompt,
            frame_count=created.settings.frame_count,
            channel=created.settings.channel,
            copy_depth=created.settings.copy_depth.value,
        )
        valid = orchestrator._materialize_plan(
            created,
            planned_story(planning_request),
        )
        one_frame_lanes = tuple(
            lane.model_copy(update={"frames": lane.frames[:1]}) for lane in valid.lanes
        )
        one_frame = PersistedStorylinePlan.model_validate(
            valid.model_dump(mode="python") | {"lanes": one_frame_lanes}
        )

        with pytest.raises(StorylineConflictError, match="between 2 and 10"):
            await orchestrator.manager.update_plan(
                created.id,
                one_frame,
                owner_id=OWNER_ID,
            )


@pytest.mark.asyncio
async def test_recovery_filter_applies_before_active_storyline_limit():
    manager = StorylineManager(store=MemoryStorylineStore())
    await manager.start()
    try:
        for index in range(100):
            request = create_request(review_plan_first=True).model_copy(
                update={"title": f"Draft storyline {index}"}
            )
            await manager.create(request, owner_id=OWNER_ID)
        queued = await manager.create(
            create_request(review_plan_first=True).model_copy(
                update={"title": "Queued storyline"}
            ),
            owner_id=OWNER_ID,
        )
        await manager.mutate_record(
            queued.id,
            owner_id=OWNER_ID,
            mutator=lambda record: record.model_copy(
                update={
                    "status": StorylineStatus.QUEUED,
                    "stage": StorylineStatus.QUEUED.value,
                }
            ),
        )

        recoverable = await manager.store.list_active(
            limit=100,
            statuses=RECONCILABLE_STORYLINE_STATUSES,
        )
        assert [record.id for record in recoverable] == [queued.id]
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_reconciler_rotates_beyond_first_hundred_active_storylines():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, _):
        await stop_storyline_reconciler(orchestrator)
        target_id = ""
        for index in range(101):
            created = await orchestrator.manager.create(
                create_request(review_plan_first=True).model_copy(
                    update={"title": f"Queued storyline {index}"}
                ),
                owner_id=OWNER_ID,
            )
            await orchestrator.manager.mutate_record(
                created.id,
                owner_id=OWNER_ID,
                mutator=lambda record: record.model_copy(
                    update={
                        "status": StorylineStatus.QUEUED,
                        "stage": StorylineStatus.QUEUED.value,
                    }
                ),
            )
            target_id = created.id

        visited: list[str] = []
        target_visited = asyncio.Event()

        async def capture(storyline_id: str) -> None:
            visited.append(storyline_id)
            if storyline_id == target_id:
                target_visited.set()

        orchestrator._reconcile_storyline = capture  # type: ignore[method-assign]
        orchestrator.reconcile_interval = 0.01
        orchestrator._reconciler = asyncio.create_task(orchestrator._reconcile_loop())

        await asyncio.wait_for(target_visited.wait(), timeout=1)
        assert target_id in visited
        assert len(set(visited)) == 101


@pytest.mark.asyncio
async def test_image_seeded_story_passes_durable_references_to_every_frame():
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, planner):
        storyline = await orchestrator.create(
            create_request(reference_count=2),
            owner_id=OWNER_ID,
        )
        await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert len(planner.requests) == 1
        assert [str(url) for url in planner.requests[0].reference_image_urls] == [
            f"https://signed.example.test/{REFERENCE_PREFIX}reference-1.png?sig=test",
            f"https://signed.example.test/{REFERENCE_PREFIX}reference-2.png?sig=test",
        ]
        assert len(runner.calls) == 3
        for call in runner.calls:
            assert call.action == PipelineAction.EDIT
            assert call.source_image_urls is None
            assert call.source_image_base64 is None
            assert call.source_image_blobs is not None
            assert [item.blob_name for item in call.source_image_blobs] == [
                f"{REFERENCE_PREFIX}reference-1.png",
                f"{REFERENCE_PREFIX}reference-2.png",
            ]


@pytest.mark.asyncio
async def test_image_seeded_flux_lane_submits_one_active_frame_at_a_time(
    monkeypatch,
):
    monkeypatch.setattr(settings, "FLUX_KONTEXT_DEPLOYMENT", "test-flux-deployment")
    first_key = (FLUX_KONTEXT_PRO_MODEL, 1)
    second_key = (FLUX_KONTEXT_PRO_MODEL, 2)
    third_key = (FLUX_KONTEXT_PRO_MODEL, 3)
    runner = RecordingRunner(blocked={first_key, second_key})
    async with running_storyline_stack(runner, concurrency=3) as (
        orchestrator,
        image_jobs,
        _,
    ):
        await stop_storyline_reconciler(orchestrator)
        storyline = await orchestrator.create(
            create_request(
                models=(FLUX_KONTEXT_PRO_MODEL,),
                reference_count=1,
            ),
            owner_id=OWNER_ID,
        )
        await asyncio.wait_for(runner.started_event(first_key).wait(), timeout=1)

        await orchestrator._reconcile_storyline(storyline.id)
        first_active = await orchestrator.get(storyline.id, owner_id=OWNER_ID)
        lane = first_active.plan.lanes[0]
        _, job_count = await image_jobs.list_jobs(owner_id=OWNER_ID, limit=20)

        assert job_count == 1
        assert lane.frames[0].status in {
            StorylineFrameStatus.QUEUED,
            StorylineFrameStatus.GENERATING,
            StorylineFrameStatus.SAVING,
        }
        assert [frame.status for frame in lane.frames[1:]] == [
            StorylineFrameStatus.PENDING,
            StorylineFrameStatus.PENDING,
        ]
        assert runner.call_counts == Counter({first_key: 1})

        runner.release(first_key)
        progressive = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: (
                item.plan.lanes[0].frames[0].status
                == StorylineFrameStatus.READY
                and runner.started_event(second_key).is_set()
            ),
        )
        lane = progressive.plan.lanes[0]
        _, job_count = await image_jobs.list_jobs(owner_id=OWNER_ID, limit=20)

        assert job_count == 2
        assert lane.frames[0].status == StorylineFrameStatus.READY
        assert lane.frames[1].status in {
            StorylineFrameStatus.QUEUED,
            StorylineFrameStatus.GENERATING,
            StorylineFrameStatus.SAVING,
        }
        assert lane.frames[2].status == StorylineFrameStatus.PENDING
        assert runner.call_counts == Counter({first_key: 1, second_key: 1})
        assert not runner.started_event(third_key).is_set()

        await orchestrator.cancel(storyline.id, owner_id=OWNER_ID)


@pytest.mark.asyncio
async def test_image_seeded_gpt_lane_submits_eligible_frames_in_parallel():
    keys = {(GPT_IMAGE_2_MODEL, order) for order in range(1, 4)}
    runner = RecordingRunner(blocked=keys)
    async with running_storyline_stack(runner, concurrency=3) as (
        orchestrator,
        image_jobs,
        _,
    ):
        await stop_storyline_reconciler(orchestrator)
        storyline = await orchestrator.create(
            create_request(reference_count=1),
            owner_id=OWNER_ID,
        )
        await asyncio.gather(
            *(
                asyncio.wait_for(runner.started_event(key).wait(), timeout=1)
                for key in keys
            )
        )

        await orchestrator._reconcile_storyline(storyline.id)
        active = await orchestrator.get(storyline.id, owner_id=OWNER_ID)
        _, job_count = await image_jobs.list_jobs(owner_id=OWNER_ID, limit=20)

        assert job_count == 3
        assert runner.call_counts == Counter({key: 1 for key in keys})
        assert all(
            frame.status
            in {
                StorylineFrameStatus.QUEUED,
                StorylineFrameStatus.GENERATING,
                StorylineFrameStatus.SAVING,
            }
            for frame in active.plan.lanes[0].frames
        )

        await orchestrator.cancel(storyline.id, owner_id=OWNER_ID)


@pytest.mark.asyncio
async def test_multiple_model_lanes_share_one_frozen_plan(monkeypatch):
    monkeypatch.setattr(settings, "FLUX_KONTEXT_DEPLOYMENT", "test-flux-deployment")
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, planner):
        storyline = await orchestrator.create(
            create_request(
                frame_count=2,
                models=(GPT_IMAGE_2_MODEL, FLUX_KONTEXT_PRO_MODEL),
                reference_count=1,
            ),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert len(planner.requests) == 1
        assert completed.plan is not None
        gpt_lane, flux_lane = completed.plan.lanes
        assert [frame.plan_frame_id for frame in gpt_lane.frames] == [
            frame.plan_frame_id for frame in flux_lane.frames
        ]
        assert [frame.purpose for frame in gpt_lane.frames] == [
            frame.purpose for frame in flux_lane.frames
        ]
        assert [frame.prompt for frame in gpt_lane.frames] == [
            frame.prompt for frame in flux_lane.frames
        ]
        assert [frame.copy_text for frame in gpt_lane.frames] == [
            frame.copy_text for frame in flux_lane.frames
        ]
        assert Counter(call.model for call in runner.calls) == {
            GPT_IMAGE_2_MODEL: 2,
            FLUX_KONTEXT_PRO_MODEL: 2,
        }


@pytest.mark.asyncio
async def test_flux_truncates_references_and_discloses_reduced_fidelity(monkeypatch):
    monkeypatch.setattr(settings, "FLUX_KONTEXT_DEPLOYMENT", "test-flux-deployment")
    runner = RecordingRunner()
    async with running_storyline_stack(runner) as (orchestrator, _, planner):
        storyline = await orchestrator.create(
            create_request(
                frame_count=2,
                models=(FLUX_KONTEXT_PRO_MODEL,),
                reference_count=3,
            ),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )

        assert len(planner.requests[0].reference_image_urls) == 3
        lane = completed.plan.lanes[0]
        assert lane.reference_image_limit == 1
        assert lane.reduced_reference_fidelity is True
        assert "Additional references are distilled into text" in (
            lane.capability_disclosure or ""
        )
        for call in runner.calls:
            assert call.source_image_blobs is not None
            assert [item.blob_name for item in call.source_image_blobs] == [
                f"{REFERENCE_PREFIX}reference-1.png"
            ]
            assert "Creative direction:" in call.prompt


@pytest.mark.asyncio
async def test_frame_completion_is_progressive_and_persisted():
    second_key = (GPT_IMAGE_2_MODEL, 2)
    runner = RecordingRunner(blocked={second_key})
    async with running_storyline_stack(runner, concurrency=2) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )
        await asyncio.wait_for(runner.started_event(second_key).wait(), timeout=1)
        progressive = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: sum(
                frame.status == StorylineFrameStatus.READY for frame in frames(item)
            )
            == 1,
        )

        assert progressive.status == StorylineStatus.GENERATING
        assert 0 < progressive.progress < 100
        persisted = await orchestrator.store.get(storyline.id, owner_id=OWNER_ID)
        assert persisted is not None
        assert persisted.revision == progressive.revision
        assert (
            sum(
                frame.status == StorylineFrameStatus.READY
                for lane in persisted.plan.lanes
                for frame in lane.frames
            )
            == 1
        )

        runner.release(second_key)
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )
        assert completed.progress == 100
        assert all(frame.asset is not None for frame in frames(completed))
        reopened = await orchestrator.get(storyline.id, owner_id=OWNER_ID)
        assert reopened == completed


@pytest.mark.asyncio
async def test_unchanged_reconciliation_does_not_churn_revision_or_etag():
    keys = {(GPT_IMAGE_2_MODEL, 1), (GPT_IMAGE_2_MODEL, 2)}
    runner = RecordingRunner(blocked=keys)
    async with running_storyline_stack(runner, concurrency=2) as (
        orchestrator,
        _,
        _,
    ):
        await stop_storyline_reconciler(orchestrator)
        storyline = await orchestrator.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )
        await asyncio.gather(
            *(
                asyncio.wait_for(runner.started_event(key).wait(), timeout=1)
                for key in keys
            )
        )

        record = await orchestrator.store.get(storyline.id, owner_id=OWNER_ID)
        first_sync = await orchestrator._sync_frame_jobs(record)
        second_sync = await orchestrator._sync_frame_jobs(first_sync)
        assert second_sync.revision == first_sync.revision
        assert second_sync.etag == first_sync.etag

        first_aggregate = await orchestrator._recompute_aggregate(storyline.id)
        second_aggregate = await orchestrator._recompute_aggregate(storyline.id)
        assert second_aggregate.revision == first_aggregate.revision
        assert second_aggregate.etag == first_aggregate.etag

        await orchestrator.cancel(storyline.id, owner_id=OWNER_ID)


@pytest.mark.asyncio
async def test_retry_resubmits_only_the_exact_failed_frame():
    failed_key = (GPT_IMAGE_2_MODEL, 2)
    runner = RecordingRunner(fail_once={failed_key})
    async with running_storyline_stack(runner, concurrency=3) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(reference_count=1),
            owner_id=OWNER_ID,
        )
        partial = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.PARTIAL,
        )
        before = {frame.order: frame for frame in frames(partial)}
        assert before[2].status == StorylineFrameStatus.FAILED

        await orchestrator.retry_frame(
            storyline.id,
            before[2].frame_id,
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )
        after = {frame.order: frame for frame in frames(completed)}

        assert runner.call_counts == Counter(
            {
                (GPT_IMAGE_2_MODEL, 1): 1,
                (GPT_IMAGE_2_MODEL, 2): 2,
                (GPT_IMAGE_2_MODEL, 3): 1,
            }
        )
        assert after[1].image_job_id == before[1].image_job_id
        assert after[1].asset == before[1].asset
        assert after[3].image_job_id == before[3].image_job_id
        assert after[3].asset == before[3].asset
        assert after[2].image_job_id != before[2].image_job_id
        assert after[2].attempt == 1
        assert after[2].status == StorylineFrameStatus.READY


@pytest.mark.asyncio
async def test_regeneration_replaces_one_frame_and_preserves_lane_context():
    runner = RecordingRunner()
    async with running_storyline_stack(runner, concurrency=2) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )
        before = {frame.order: frame for frame in frames(completed)}

        await orchestrator.regenerate_frame(
            storyline.id,
            before[2].frame_id,
            owner_id=OWNER_ID,
            prompt="Move the same hero product into a dramatic night scene.",
            copy_text="Own the night.",
        )
        regenerated = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED
            and {frame.order: frame for frame in frames(item)}[2].attempt == 1,
        )
        after = {frame.order: frame for frame in frames(regenerated)}

        assert runner.call_counts == Counter(
            {
                (GPT_IMAGE_2_MODEL, 1): 1,
                (GPT_IMAGE_2_MODEL, 2): 2,
            }
        )
        assert after[1].image_job_id == before[1].image_job_id
        assert after[1].asset == before[1].asset
        assert after[2].image_job_id != before[2].image_job_id
        assert after[2].asset != before[2].asset
        assert after[2].prompt == (
            "Move the same hero product into a dramatic night scene."
        )
        assert after[2].copy_text == "Own the night."
        last_request = runner.calls[-1]
        assert "dramatic night scene" in last_request.prompt
        assert last_request.metadata["storyline_copy"] == "Own the night."
        assert last_request.source_image_blobs is not None
        assert last_request.source_image_blobs[0].blob_name == (
            f"{REFERENCE_PREFIX}reference-1.png"
        )


@pytest.mark.asyncio
async def test_regeneration_is_rejected_until_active_generation_settles():
    active_key = (GPT_IMAGE_2_MODEL, 2)
    runner = RecordingRunner(blocked={active_key})
    async with running_storyline_stack(runner, concurrency=2) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )
        await asyncio.wait_for(runner.started_event(active_key).wait(), timeout=1)
        progressive = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.plan.lanes[0].frames[0].status
            == StorylineFrameStatus.READY,
        )

        with pytest.raises(
            StorylineConflictError, match="after storyline generation settles"
        ):
            await orchestrator.regenerate_frame(
                storyline.id,
                progressive.plan.lanes[0].frames[0].frame_id,
                owner_id=OWNER_ID,
            )
        assert runner.call_counts == Counter(
            {
                (GPT_IMAGE_2_MODEL, 1): 1,
                (GPT_IMAGE_2_MODEL, 2): 1,
            }
        )

        runner.release(active_key)
        await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )


@pytest.mark.asyncio
async def test_text_anchor_regeneration_cascades_to_all_lane_dependents(
    monkeypatch,
):
    monkeypatch.setattr(settings, "FLUX_KONTEXT_DEPLOYMENT", "test-flux-deployment")
    runner = RecordingRunner()
    async with running_storyline_stack(runner, concurrency=4) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(
                frame_count=2,
                models=(GPT_IMAGE_2_MODEL, FLUX_KONTEXT_PRO_MODEL),
            ),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )
        before = {
            (lane.model, frame.order): frame
            for lane in completed.plan.lanes
            for frame in lane.frames
        }

        await orchestrator.regenerate_frame(
            storyline.id,
            before[(GPT_IMAGE_2_MODEL, 1)].frame_id,
            owner_id=OWNER_ID,
            prompt="A revised opening scene shared by both model lanes.",
        )
        regenerated = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED
            and all(frame.attempt == 1 for frame in frames(item)),
        )
        after = {
            (lane.model, frame.order): frame
            for lane in regenerated.plan.lanes
            for frame in lane.frames
        }

        assert runner.call_counts == Counter(
            {
                (GPT_IMAGE_2_MODEL, 1): 2,
                (GPT_IMAGE_2_MODEL, 2): 2,
                (FLUX_KONTEXT_PRO_MODEL, 1): 2,
                (FLUX_KONTEXT_PRO_MODEL, 2): 2,
            }
        )
        for key, original in before.items():
            assert after[key].image_job_id != original.image_job_id
            assert after[key].asset != original.asset
        assert {
            after[(model, 1)].prompt
            for model in (GPT_IMAGE_2_MODEL, FLUX_KONTEXT_PRO_MODEL)
        } == {"A revised opening scene shared by both model lanes."}


@pytest.mark.asyncio
async def test_copy_only_edit_rerenders_target_but_preserves_sibling_lane_assets(
    monkeypatch,
):
    monkeypatch.setattr(settings, "FLUX_KONTEXT_DEPLOYMENT", "test-flux-deployment")
    runner = RecordingRunner()
    async with running_storyline_stack(runner, concurrency=4) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(
                frame_count=2,
                models=(GPT_IMAGE_2_MODEL, FLUX_KONTEXT_PRO_MODEL),
                reference_count=1,
            ),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )
        before = {
            (lane.model, frame.order): frame
            for lane in completed.plan.lanes
            for frame in lane.frames
        }

        await orchestrator.regenerate_frame(
            storyline.id,
            before[(GPT_IMAGE_2_MODEL, 2)].frame_id,
            owner_id=OWNER_ID,
            copy_text="Revised copy shared without rerendering the sibling lane.",
        )
        regenerated = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED
            and next(
                lane for lane in item.plan.lanes if lane.model == GPT_IMAGE_2_MODEL
            )
            .frames[1]
            .attempt
            == 1,
        )
        after = {
            (lane.model, frame.order): frame
            for lane in regenerated.plan.lanes
            for frame in lane.frames
        }

        assert runner.call_counts == Counter(
            {
                (GPT_IMAGE_2_MODEL, 1): 1,
                (GPT_IMAGE_2_MODEL, 2): 2,
                (FLUX_KONTEXT_PRO_MODEL, 1): 1,
                (FLUX_KONTEXT_PRO_MODEL, 2): 1,
            }
        )
        target = after[(GPT_IMAGE_2_MODEL, 2)]
        sibling = after[(FLUX_KONTEXT_PRO_MODEL, 2)]
        assert target.image_job_id != before[(GPT_IMAGE_2_MODEL, 2)].image_job_id
        assert sibling.image_job_id == before[(FLUX_KONTEXT_PRO_MODEL, 2)].image_job_id
        assert sibling.asset == before[(FLUX_KONTEXT_PRO_MODEL, 2)].asset
        assert (
            target.copy_text
            == sibling.copy_text
            == ("Revised copy shared without rerendering the sibling lane.")
        )


@pytest.mark.asyncio
async def test_seeded_anchor_regeneration_does_not_reset_independent_frames():
    runner = RecordingRunner()
    async with running_storyline_stack(runner, concurrency=3) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(frame_count=3, reference_count=1),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )
        before = {frame.order: frame for frame in frames(completed)}

        await orchestrator.regenerate_frame(
            storyline.id,
            before[1].frame_id,
            owner_id=OWNER_ID,
        )
        regenerated = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED
            and {frame.order: frame for frame in frames(item)}[1].attempt == 1,
        )
        after = {frame.order: frame for frame in frames(regenerated)}

        assert runner.call_counts == Counter(
            {
                (GPT_IMAGE_2_MODEL, 1): 2,
                (GPT_IMAGE_2_MODEL, 2): 1,
                (GPT_IMAGE_2_MODEL, 3): 1,
            }
        )
        assert after[1].image_job_id != before[1].image_job_id
        for order in (2, 3):
            assert after[order].image_job_id == before[order].image_job_id
            assert after[order].asset == before[order].asset


@pytest.mark.asyncio
async def test_cancellation_stops_jobs_and_terminal_cancellation_is_a_noop():
    keys = {(GPT_IMAGE_2_MODEL, 1), (GPT_IMAGE_2_MODEL, 2)}
    runner = RecordingRunner(blocked=keys)
    async with running_storyline_stack(runner, concurrency=2) as (
        orchestrator,
        image_jobs,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )
        await asyncio.gather(
            *(
                asyncio.wait_for(runner.started_event(key).wait(), timeout=1)
                for key in keys
            )
        )

        cancelled = await orchestrator.cancel(storyline.id, owner_id=OWNER_ID)
        assert cancelled.status == StorylineStatus.CANCELLED
        assert cancelled.cancel_requested is True
        assert all(
            frame.status == StorylineFrameStatus.CANCELLED
            for frame in frames(cancelled)
        )
        async with asyncio.timeout(2):
            while runner.cancelled != keys:
                await asyncio.sleep(0.01)
        jobs, total = await image_jobs.list_jobs(owner_id=OWNER_ID, limit=10)
        assert total == 2
        assert all(
            job.status in {ImageJobStatus.CANCELLED, ImageJobStatus.CANCEL_REQUESTED}
            for job in jobs
        )

    completed_runner = RecordingRunner()
    async with running_storyline_stack(completed_runner) as (
        orchestrator,
        _,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )
        completed = await wait_for_storyline(
            orchestrator,
            storyline.id,
            lambda item: item.status == StorylineStatus.COMPLETED,
        )
        unchanged = await orchestrator.cancel(storyline.id, owner_id=OWNER_ID)
        assert unchanged.status == StorylineStatus.COMPLETED
        assert unchanged.revision == completed.revision
        assert unchanged.cancel_requested is False


@pytest.mark.asyncio
async def test_cancellation_syncs_completed_child_assets_before_finalizing():
    runner = RecordingRunner()
    async with running_storyline_stack(runner, concurrency=2) as (
        orchestrator,
        image_jobs,
        _,
    ):
        await stop_storyline_reconciler(orchestrator)
        storyline = await orchestrator.create(
            create_request(frame_count=2, reference_count=1),
            owner_id=OWNER_ID,
        )
        async with asyncio.timeout(2):
            while True:
                jobs, total = await image_jobs.list_jobs(owner_id=OWNER_ID, limit=10)
                if total == 2 and all(
                    job.status == ImageJobStatus.COMPLETED for job in jobs
                ):
                    break
                await asyncio.sleep(0.01)

        stale = await orchestrator.get(storyline.id, owner_id=OWNER_ID)
        assert any(
            frame.status != StorylineFrameStatus.READY for frame in frames(stale)
        )
        cancelled = await orchestrator.cancel(storyline.id, owner_id=OWNER_ID)

        assert cancelled.status == StorylineStatus.COMPLETED
        assert cancelled.cancel_requested is False
        assert all(
            frame.status == StorylineFrameStatus.READY for frame in frames(cancelled)
        )
        assert all(frame.asset is not None for frame in frames(cancelled))


@pytest.mark.asyncio
async def test_remote_cancel_between_submit_and_attach_cannot_resurrect_frames():
    keys = {(GPT_IMAGE_2_MODEL, 1), (GPT_IMAGE_2_MODEL, 2)}
    runner = RecordingRunner(blocked=keys)
    async with running_storyline_stack(runner, concurrency=2) as (
        orchestrator,
        image_jobs,
        _,
    ):
        storyline = await orchestrator.create(
            create_request(
                frame_count=2,
                reference_count=1,
                review_plan_first=True,
            ),
            owner_id=OWNER_ID,
        )
        original_submit = image_jobs.submit
        cancelled_remotely = False

        async def submit_with_remote_cancel(
            request,
            *,
            owner_id,
            parent_job_id=None,
            **kwargs,
        ):
            nonlocal cancelled_remotely
            job = await original_submit(
                request,
                owner_id=owner_id,
                parent_job_id=parent_job_id,
                **kwargs,
            )
            if not cancelled_remotely:
                cancelled_remotely = True
                await orchestrator.manager.cancel(storyline.id, owner_id=OWNER_ID)
            return job

        image_jobs.submit = submit_with_remote_cancel  # type: ignore[method-assign]
        result = await orchestrator.start_generation(
            storyline.id,
            owner_id=OWNER_ID,
        )

        assert result.status == StorylineStatus.CANCELLED
        assert all(
            frame.status == StorylineFrameStatus.CANCELLED
            and frame.image_job_id is None
            for frame in frames(result)
        )
        async with asyncio.timeout(2):
            while True:
                jobs, total = await image_jobs.list_jobs(owner_id=OWNER_ID, limit=10)
                if total == 1 and all(
                    job.status
                    in {ImageJobStatus.CANCELLED, ImageJobStatus.CANCEL_REQUESTED}
                    for job in jobs
                ):
                    break
                await asyncio.sleep(0.01)
