"""Durable storyline planning and frame orchestration.

Storylines are persisted as first-class aggregates, while each rendered frame is
executed by the existing durable image-job service.  This keeps provider calls,
leases, cancellation, saving, analysis, and dead-letter behavior in one place.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from backend.core.config import settings
from backend.core.image_capabilities import (
    get_configured_image_model_capabilities,
    get_image_model_capabilities,
    validate_image_output_constraints,
    validate_compatible_image_size,
)
from backend.core.sas import get_blob_container_url, get_container_sas_token
from backend.core.storyline_planner import StorylinePlanner
from backend.jobs.manager import ImageJobManager, ImageJobNotFoundError
from backend.models.image_jobs import (
    TERMINAL_IMAGE_JOB_STATUSES,
    ImageJob,
    ImageJobCreateRequest,
    ImageJobOutputStatus,
    ImageJobStatus,
)
from backend.models.images import (
    FLUX_KONTEXT_PRO_MODEL,
    ImagePipelineRequest,
    PipelineAction,
    PipelineAnalysisOptions,
    PipelineImageReference,
    PipelineSaveOptions,
)
from backend.models.storyline_planning import (
    StorylinePlan as PlannedStoryline,
    StorylinePlanningRequest,
)
from backend.models.storylines import (
    TERMINAL_STORYLINE_STATUSES,
    Storyline,
    StorylineCreateRequest,
    StorylineFrame,
    StorylineFrameAsset,
    StorylineFrameStatus,
    StorylineLane,
    StorylinePlan,
    StorylineRecord,
    StorylineReference,
    StorylineStatus,
    build_storyline_image_prompt,
)
from backend.storylines.manager import (
    StorylineConflictError,
    StorylineManager,
    StorylineNotFoundError,
)
from backend.storylines.references import is_owned_storyline_reference

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


ReferenceUrlBuilder = Callable[[StorylineReference], Awaitable[str]]
RECONCILABLE_STORYLINE_STATUSES = {
    StorylineStatus.QUEUED,
    StorylineStatus.GENERATING,
    StorylineStatus.CANCEL_REQUESTED,
}


class StorylineOrchestrator:
    """Coordinate a shared plan and model-specific durable frame jobs."""

    def __init__(
        self,
        *,
        manager: StorylineManager,
        image_jobs: ImageJobManager,
        planner: StorylinePlanner,
        reconcile_interval: float = 1.0,
        reference_url_builder: ReferenceUrlBuilder | None = None,
    ) -> None:
        self.manager = manager
        self.image_jobs = image_jobs
        self.planner = planner
        self.reconcile_interval = max(0.1, reconcile_interval)
        self.reference_url_builder = (
            reference_url_builder or self._build_signed_reference_url
        )
        self._reconciler: asyncio.Task[None] | None = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._started = False

    @property
    def store(self):
        return self.manager.store

    async def start(self) -> None:
        if self._started:
            return
        await self.manager.start()
        self._reconciler = asyncio.create_task(
            self._reconcile_loop(),
            name="storyline-reconciler",
        )
        self._started = True

    async def close(self) -> None:
        if not self._started:
            return
        reconciler, self._reconciler = self._reconciler, None
        if reconciler is not None:
            reconciler.cancel()
            await asyncio.gather(reconciler, return_exceptions=True)
        self._locks.clear()
        await self.manager.close()
        self._started = False

    async def health_check(self) -> None:
        await self.manager.health_check()
        if self._reconciler is None or self._reconciler.done():
            raise RuntimeError("Storyline reconciler is not running")

    def capabilities(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            capability.to_public_dict()
            for capability in get_configured_image_model_capabilities(settings)
        )

    async def create(
        self,
        request: StorylineCreateRequest,
        *,
        owner_id: str,
    ) -> Storyline:
        self._validate_create_request(request, owner_id=owner_id)
        storyline = await self.manager.create(request, owner_id=owner_id)
        if storyline.plan is not None:
            if (
                not storyline.settings.review_plan_first
                and storyline.status == StorylineStatus.PLANNED
            ):
                return await self.start_generation(
                    storyline.id,
                    owner_id=owner_id,
                )
            return storyline

        try:
            planned = await self.planner.plan(
                StorylinePlanningRequest(
                    prompt=(
                        storyline.settings.prompt.strip()
                        or "Create a coherent visual storyline from the supplied reference images."
                    ),
                    frame_count=storyline.settings.frame_count,
                    channel=storyline.settings.channel,
                    copy_depth=storyline.settings.copy_depth.value,
                    reference_image_urls=[
                        await self.reference_url_builder(reference)
                        for reference in storyline.references
                    ],
                )
            )
            plan = self._materialize_plan(storyline, planned)
            try:
                storyline = await self.manager.update_plan(
                    storyline.id,
                    plan,
                    owner_id=owner_id,
                    expected_revision=storyline.revision,
                )
            except StorylineConflictError:
                # Concurrent idempotent creates may both plan the same draft. If
                # another caller already committed the shared plan, use that
                # winner rather than turning a healthy aggregate into a planning
                # failure from the losing stale revision.
                current = await self.manager.store.get(
                    storyline.id,
                    owner_id=owner_id,
                )
                if current is None or current.plan is None:
                    raise
                storyline = self.manager.to_public(current)
        except Exception as exc:
            logger.exception("Storyline planning failed for %s", storyline.id)
            await self._mark_planning_failed(
                storyline.id,
                owner_id,
                exc,
                expected_revision=storyline.revision,
            )
            raise

        if not storyline.settings.review_plan_first:
            storyline = await self.start_generation(
                storyline.id,
                owner_id=owner_id,
            )
        return storyline

    @staticmethod
    def _validate_create_request(
        request: StorylineCreateRequest,
        *,
        owner_id: str,
    ) -> None:
        wrong_containers = {
            reference.container
            for reference in request.references
            if reference.container != settings.AZURE_BLOB_IMAGE_CONTAINER
        }
        if wrong_containers:
            raise StorylineConflictError(
                "Storyline references must come from the configured image container"
            )
        if any(
            not is_owned_storyline_reference(reference.blob_name, owner_id)
            for reference in request.references
        ):
            raise StorylineConflictError(
                "One or more storyline references do not belong to this owner"
            )

        configured = {
            item.model for item in get_configured_image_model_capabilities(settings)
        }
        missing = set(request.settings.models) - configured
        if missing:
            raise StorylineConflictError(
                "The following image models are not configured: "
                + ", ".join(sorted(missing))
            )
        try:
            for model in request.settings.models:
                validate_compatible_image_size(model, request.settings.size)
                validate_image_output_constraints(
                    model,
                    provider=settings.MODEL_PROVIDER,
                    output_count=1,
                    output_format=request.settings.output_format,
                    background=request.settings.background,
                )
        except ValueError as exc:
            raise StorylineConflictError(str(exc)) from exc

    async def get(self, storyline_id: str, *, owner_id: str) -> Storyline:
        return await self.manager.get(storyline_id, owner_id=owner_id)

    async def retry_planning(
        self,
        storyline_id: str,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> Storyline:
        """Recover a draft or planning failure without creating a new aggregate."""

        async with self._storyline_lock(storyline_id):
            now = utcnow()

            def begin(record: StorylineRecord) -> StorylineRecord:
                if record.plan is not None:
                    return record
                if record.status != StorylineStatus.DRAFT and not (
                    record.status == StorylineStatus.FAILED
                    and record.stage == "planning_failed"
                ):
                    raise StorylineConflictError(
                        "Only an unfinished or failed storyline plan can be retried"
                    )
                return record.model_copy(
                    update={
                        "status": StorylineStatus.DRAFT,
                        "stage": "planning",
                        "progress": 0,
                        "error": None,
                        "completed_at": None,
                        "updated_at": now,
                    }
                )

            record = await self.manager.mutate_record(
                storyline_id,
                owner_id=owner_id,
                mutator=begin,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
            if record.plan is not None:
                planned_storyline = self.manager.to_public(record)
            else:
                try:
                    planned = await self.planner.plan(
                        StorylinePlanningRequest(
                            prompt=(
                                record.settings.prompt.strip()
                                or (
                                    "Create a coherent visual storyline from the "
                                    "supplied reference images."
                                )
                            ),
                            frame_count=record.settings.frame_count,
                            channel=record.settings.channel,
                            copy_depth=record.settings.copy_depth.value,
                            reference_image_urls=[
                                await self.reference_url_builder(reference)
                                for reference in record.references
                            ],
                        )
                    )
                    plan = self._materialize_plan(
                        self.manager.to_public(record), planned
                    )
                    planned_storyline = await self.manager.update_plan(
                        storyline_id,
                        plan,
                        owner_id=owner_id,
                        expected_revision=record.revision,
                    )
                except Exception as exc:
                    await self._mark_planning_failed(
                        storyline_id,
                        owner_id,
                        exc,
                        expected_revision=record.revision,
                    )
                    raise

        if not planned_storyline.settings.review_plan_first:
            return await self.start_generation(
                storyline_id,
                owner_id=owner_id,
            )
        return planned_storyline

    async def list_storylines(
        self,
        *,
        owner_id: str,
        limit: int,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> tuple[list[Storyline], int]:
        return await self.manager.list_storylines(
            owner_id=owner_id,
            limit=limit,
            offset=offset,
            statuses=statuses,
        )

    async def update_plan(
        self,
        storyline_id: str,
        plan: StorylinePlan,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> Storyline:
        return await self.manager.update_plan(
            storyline_id,
            plan,
            owner_id=owner_id,
            expected_revision=expected_revision,
            expected_etag=expected_etag,
        )

    async def start_generation(
        self,
        storyline_id: str,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> Storyline:
        now = utcnow()

        def queue(record: StorylineRecord) -> StorylineRecord:
            if record.plan is None:
                raise StorylineConflictError(
                    "The storyline must have a reviewed plan before generation"
                )
            if record.status in {StorylineStatus.QUEUED, StorylineStatus.GENERATING}:
                return record
            if record.status not in {
                StorylineStatus.PLANNED,
            }:
                raise StorylineConflictError(
                    f"A storyline cannot start from {record.status.value}"
                )
            return record.model_copy(
                update={
                    "status": StorylineStatus.QUEUED,
                    "stage": StorylineStatus.QUEUED.value,
                    "error": None,
                    "cancel_requested": False,
                    "completed_at": None,
                    "updated_at": now,
                }
            )

        async with self._storyline_lock(storyline_id):
            record = await self.manager.mutate_record(
                storyline_id,
                owner_id=owner_id,
                mutator=queue,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
            await self._reconcile_storyline_locked(storyline_id)
            latest = await self.manager.store.get(storyline_id, owner_id=owner_id)
            return self.manager.to_public(latest or record)

    async def cancel(
        self,
        storyline_id: str,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> Storyline:
        now = utcnow()

        def request_cancel(record: StorylineRecord) -> StorylineRecord:
            if record.status in TERMINAL_STORYLINE_STATUSES:
                return record
            return record.model_copy(
                update={
                    "status": StorylineStatus.CANCEL_REQUESTED,
                    "stage": StorylineStatus.CANCEL_REQUESTED.value,
                    "cancel_requested": True,
                    "updated_at": now,
                }
            )

        async with self._storyline_lock(storyline_id):
            existing = await self.manager.store.get(
                storyline_id,
                owner_id=owner_id,
            )
            if existing is None:
                raise StorylineNotFoundError(storyline_id)
            if existing.status in TERMINAL_STORYLINE_STATUSES:
                return self.manager.to_public(existing)
            record = await self.manager.mutate_record(
                storyline_id,
                owner_id=owner_id,
                mutator=request_cancel,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
            await self._cancel_image_jobs(record)
            record = await self._sync_frame_jobs(record)
            final = (
                await self._recompute_aggregate(storyline_id)
                if self._all_frames_ready(record)
                else await self._mark_cancelled(storyline_id, owner_id=owner_id)
            )
            return self.manager.to_public(final)

    async def retry_frame(
        self,
        storyline_id: str,
        frame_id: str,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
        prompt: str | None = None,
        copy_text: str | None = None,
    ) -> Storyline:
        async with self._storyline_lock(storyline_id):
            existing = await self.manager.store.get(storyline_id, owner_id=owner_id)
            if existing is None:
                raise StorylineNotFoundError(storyline_id)
            current_frame = self._find_frame(existing, frame_id)
            frames_to_cancel = self._frames_invalidated_by_edit(
                existing,
                current_frame,
                prompt=prompt,
                copy_text=copy_text,
            )
            await self._cancel_frames(frames_to_cancel, owner_id=owner_id)
            await self.manager.retry_frame(
                storyline_id,
                frame_id,
                owner_id=owner_id,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                prompt=prompt,
                copy_text=copy_text,
            )
            await self._reconcile_storyline_locked(storyline_id)
            return await self.manager.get(storyline_id, owner_id=owner_id)

    async def regenerate_frame(
        self,
        storyline_id: str,
        frame_id: str,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
        prompt: str | None = None,
        copy_text: str | None = None,
    ) -> Storyline:
        async with self._storyline_lock(storyline_id):
            existing = await self.manager.store.get(storyline_id, owner_id=owner_id)
            if existing is None:
                raise StorylineNotFoundError(storyline_id)
            if existing.status not in TERMINAL_STORYLINE_STATUSES:
                raise StorylineConflictError(
                    "A frame can only be regenerated after storyline generation settles"
                )
            current_frame = self._find_frame(existing, frame_id)
            frames_to_cancel = self._frames_invalidated_by_edit(
                existing,
                current_frame,
                prompt=prompt,
                copy_text=copy_text,
            )
            await self._cancel_frames(frames_to_cancel, owner_id=owner_id)
            await self.manager.regenerate_frame(
                storyline_id,
                frame_id,
                owner_id=owner_id,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                prompt=prompt,
                copy_text=copy_text,
            )
            await self._reconcile_storyline_locked(storyline_id)
            return await self.manager.get(storyline_id, owner_id=owner_id)

    @staticmethod
    def _frames_invalidated_by_edit(
        record: StorylineRecord,
        target: StorylineFrame,
        *,
        prompt: str | None,
        copy_text: str | None,
    ) -> list[StorylineFrame]:
        prompt_changed = prompt is not None and prompt != target.prompt
        if record.plan is None:
            return [target]
        affected_lane_ids = (
            {lane.lane_id for lane in record.plan.lanes}
            if prompt_changed
            else {target.lane_id}
        )
        return [
            frame
            for lane in record.plan.lanes
            for frame in lane.frames
            if (
                frame.frame_id == target.frame_id
                or (prompt_changed and frame.plan_frame_id == target.plan_frame_id)
                or (
                    not record.references
                    and target.order == 1
                    and frame.lane_id in affected_lane_ids
                    and frame.order > 1
                )
            )
        ]

    async def _cancel_frames(
        self,
        frames: list[StorylineFrame],
        *,
        owner_id: str,
    ) -> None:
        for frame in frames:
            if not frame.image_job_id:
                continue
            try:
                await self.image_jobs.cancel(
                    frame.image_job_id,
                    owner_id=owner_id,
                )
            except ImageJobNotFoundError:
                pass

    async def _reconcile_loop(self) -> None:
        while True:
            try:
                active: list[StorylineRecord] = []
                offset = 0
                while True:
                    page = await self.manager.store.list_active(
                        limit=100,
                        offset=offset,
                        statuses=RECONCILABLE_STORYLINE_STATUSES,
                    )
                    active.extend(page)
                    if len(page) < 100:
                        break
                    offset += len(page)
                for record in active:
                    try:
                        await self._reconcile_storyline(record.id)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception("Failed to reconcile storyline %s", record.id)
                await asyncio.sleep(self.reconcile_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Storyline reconciliation loop failed")
                await asyncio.sleep(self.reconcile_interval)

    async def _reconcile_storyline(self, storyline_id: str) -> None:
        async with self._storyline_lock(storyline_id):
            await self._reconcile_storyline_locked(storyline_id)

    def _storyline_lock(self, storyline_id: str) -> asyncio.Lock:
        return self._locks.setdefault(storyline_id, asyncio.Lock())

    async def _reconcile_storyline_locked(self, storyline_id: str) -> None:
        record = await self.manager.store.get(storyline_id)
        if record is None or record.plan is None:
            return
        if record.status == StorylineStatus.CANCEL_REQUESTED:
            await self._cancel_image_jobs(record)
            record = await self._sync_frame_jobs(record)
            if self._all_frames_ready(record):
                await self._recompute_aggregate(storyline_id)
            else:
                await self._mark_cancelled(storyline_id, owner_id=record.owner_id)
            return
        if record.status not in {
            StorylineStatus.QUEUED,
            StorylineStatus.GENERATING,
        }:
            return

        record = await self._sync_frame_jobs(record)
        record = await self._submit_eligible_frames(record)
        await self._recompute_aggregate(record.id)

    async def _sync_frame_jobs(self, record: StorylineRecord) -> StorylineRecord:
        assert record.plan is not None
        frames = [frame for lane in record.plan.lanes for frame in lane.frames]
        jobs: dict[str, tuple[str, ImageJob | None]] = {}
        for frame in frames:
            if not frame.image_job_id:
                continue
            try:
                jobs[frame.frame_id] = (
                    frame.image_job_id,
                    await self.image_jobs.get(
                        frame.image_job_id,
                        owner_id=record.owner_id,
                    ),
                )
            except ImageJobNotFoundError:
                jobs[frame.frame_id] = (frame.image_job_id, None)
        if not jobs:
            return record

        now = utcnow()

        def update_frame(frame: StorylineFrame) -> StorylineFrame:
            if frame.frame_id not in jobs:
                return frame
            expected_job_id, job = jobs[frame.frame_id]
            if frame.image_job_id != expected_job_id:
                return frame
            return self._frame_from_job(frame, job)

        synchronized_plan = self._map_frames(record.plan, update_frame)
        if synchronized_plan == record.plan:
            return record

        def synchronize(current: StorylineRecord) -> StorylineRecord:
            if current.plan is None:
                return current

            return current.model_copy(
                update={
                    "plan": self._map_frames(current.plan, update_frame),
                    "updated_at": now,
                }
            )

        return await self.manager.mutate_record(
            record.id,
            owner_id=None,
            mutator=synchronize,
        )

    async def _submit_eligible_frames(self, record: StorylineRecord) -> StorylineRecord:
        if record.plan is None:
            return record
        for lane in record.plan.lanes:
            lane_record = await self.manager.store.get(record.id)
            if lane_record is None or lane_record.plan is None:
                return record
            live_lane = next(
                item for item in lane_record.plan.lanes if item.lane_id == lane.lane_id
            )
            serialize_lane = live_lane.model == FLUX_KONTEXT_PRO_MODEL
            if serialize_lane and await self._lane_has_active_frame_job(
                live_lane,
                owner_id=lane_record.owner_id,
            ):
                continue
            for frame in live_lane.frames:
                if frame.status != StorylineFrameStatus.PENDING:
                    continue
                sources = self._frame_sources(lane_record, live_lane, frame)
                if sources is None:
                    continue
                request = self._build_frame_request(
                    lane_record,
                    live_lane,
                    frame,
                    sources=sources,
                )
                image_job = await self.image_jobs.submit(
                    ImageJobCreateRequest(
                        request=request,
                        idempotency_key=(
                            f"storyline:{record.id}:frame:{frame.frame_id}:"
                            f"attempt:{frame.attempt}"
                        ),
                        client_request_id=frame.frame_id,
                    ),
                    owner_id=record.owner_id,
                    allow_durable_edit=True,
                )
                attached = await self._attach_job(
                    record.id,
                    frame.frame_id,
                    image_job.id,
                    expected_attempt=frame.attempt,
                )
                if not attached:
                    try:
                        await self.image_jobs.cancel(
                            image_job.id,
                            owner_id=record.owner_id,
                        )
                    except ImageJobNotFoundError:
                        pass
                    # A lost attach means another replica changed the aggregate
                    # (most importantly, it may have been cancelled). Stop using
                    # this lane snapshot before submitting any more provider work.
                    return await self.manager.store.get(record.id) or record
                if serialize_lane:
                    # FLUX capacity is substantially lower than the other image
                    # providers. Advance one durable frame job at a time so
                    # simultaneously eligible frames do not consume their retry
                    # budgets in a synchronized 429 burst.
                    break
        return await self.manager.store.get(record.id) or record

    async def _lane_has_active_frame_job(
        self,
        lane: StorylineLane,
        *,
        owner_id: str,
    ) -> bool:
        active_frame_statuses = {
            StorylineFrameStatus.QUEUED,
            StorylineFrameStatus.GENERATING,
            StorylineFrameStatus.SAVING,
        }
        for frame in lane.frames:
            if frame.status in active_frame_statuses:
                return True
            if not frame.image_job_id:
                continue
            try:
                job = await self.image_jobs.get(
                    frame.image_job_id,
                    owner_id=owner_id,
                )
            except ImageJobNotFoundError:
                continue
            if job.status not in TERMINAL_IMAGE_JOB_STATUSES:
                return True
        return False

    def _frame_sources(
        self,
        record: StorylineRecord,
        lane: StorylineLane,
        frame: StorylineFrame,
    ) -> tuple[PipelineImageReference, ...] | None:
        capabilities = get_image_model_capabilities(
            lane.model,
            provider=settings.MODEL_PROVIDER,
        )
        if record.references:
            references = record.references[: capabilities.max_reference_images]
            return tuple(self._reference_to_pipeline(item) for item in references)
        if frame.order == 1:
            return ()
        anchor = lane.frames[0]
        if anchor.status != StorylineFrameStatus.READY or anchor.asset is None:
            return None
        if not anchor.asset.container:
            raise RuntimeError("The generated storyline anchor has no container")
        return (
            PipelineImageReference(
                blob_name=anchor.asset.blob_name,
                container=anchor.asset.container,
                content_type=anchor.asset.content_type,
                original_filename=anchor.asset.blob_name.rsplit("/", 1)[-1],
            ),
        )

    def _build_frame_request(
        self,
        record: StorylineRecord,
        lane: StorylineLane,
        frame: StorylineFrame,
        *,
        sources: tuple[PipelineImageReference, ...],
    ) -> ImagePipelineRequest:
        assert record.plan is not None
        direction = record.plan.creative_direction
        prompt = build_storyline_image_prompt(
            direction,
            purpose=frame.purpose,
            frame_prompt=frame.prompt,
        )
        action = PipelineAction.EDIT if sources else PipelineAction.GENERATE
        metadata = {
            "storyline_id": record.id,
            "storyline_title": record.title,
            "storyline_lane_id": lane.lane_id,
            "storyline_frame_id": frame.frame_id,
            "storyline_plan_frame_id": frame.plan_frame_id,
            "storyline_frame_index": frame.order,
            "storyline_frame_count": record.settings.frame_count,
            "storyline_frame_purpose": frame.purpose,
            "storyline_copy": frame.copy_text,
            "storyline_channel": record.settings.channel,
            "storyline_copy_depth": record.settings.copy_depth.value,
            "storyline_plan_version": record.plan.version,
            "storyline_creative_direction": direction.model_dump(mode="json"),
        }
        return ImagePipelineRequest(
            action=action,
            prompt=prompt,
            model=lane.model,
            n=1,
            size=record.settings.size,
            response_format="b64_json",
            quality=record.settings.quality,
            output_format=record.settings.output_format,
            output_compression=record.settings.output_compression,
            background=record.settings.background,
            input_fidelity=record.settings.input_fidelity,
            source_image_blobs=list(sources) or None,
            save_options=PipelineSaveOptions(
                enabled=True,
                save_all=True,
                folder_path=record.settings.folder_path,
                output_format=record.settings.output_format,
                background=record.settings.background,
                metadata=metadata,
            ),
            analysis_options=PipelineAnalysisOptions(
                enabled=record.settings.analysis_enabled,
            ),
            metadata=metadata,
        )

    async def _attach_job(
        self,
        storyline_id: str,
        frame_id: str,
        image_job_id: str,
        *,
        expected_attempt: int,
    ) -> bool:
        now = utcnow()
        attached = False

        def attach(record: StorylineRecord) -> StorylineRecord:
            nonlocal attached
            attached = False
            if (
                record.plan is None
                or record.cancel_requested
                or record.status
                not in {StorylineStatus.QUEUED, StorylineStatus.GENERATING}
            ):
                return record

            def update(frame: StorylineFrame) -> StorylineFrame:
                nonlocal attached
                if frame.frame_id != frame_id:
                    return frame
                if frame.attempt != expected_attempt:
                    return frame
                if frame.image_job_id == image_job_id:
                    attached = True
                    return frame
                if (
                    frame.status != StorylineFrameStatus.PENDING
                    or frame.image_job_id is not None
                ):
                    return frame
                payload = frame.model_dump(mode="python")
                payload.update(
                    {
                        "image_job_id": image_job_id,
                        "status": StorylineFrameStatus.QUEUED,
                        "asset": None,
                        "error": None,
                    }
                )
                attached = True
                return StorylineFrame.model_validate(payload)

            return record.model_copy(
                update={
                    "plan": self._map_frames(record.plan, update),
                    "status": StorylineStatus.GENERATING,
                    "stage": StorylineStatus.GENERATING.value,
                    "updated_at": now,
                }
            )

        await self.manager.mutate_record(
            storyline_id,
            owner_id=None,
            mutator=attach,
        )
        return attached

    async def _recompute_aggregate(self, storyline_id: str) -> StorylineRecord:
        now = utcnow()

        def recompute(record: StorylineRecord) -> StorylineRecord:
            if record.plan is None:
                return record
            frames = [frame for lane in record.plan.lanes for frame in lane.frames]
            if not frames:
                return record
            ready = sum(frame.status == StorylineFrameStatus.READY for frame in frames)
            failed = sum(
                frame.status == StorylineFrameStatus.FAILED for frame in frames
            )
            cancelled = sum(
                frame.status == StorylineFrameStatus.CANCELLED for frame in frames
            )
            terminal = ready + failed + cancelled
            weights = {
                StorylineFrameStatus.PENDING: 0,
                StorylineFrameStatus.QUEUED: 5,
                StorylineFrameStatus.GENERATING: 40,
                StorylineFrameStatus.SAVING: 80,
                StorylineFrameStatus.READY: 100,
                StorylineFrameStatus.FAILED: 100,
                StorylineFrameStatus.CANCELLED: 100,
            }
            progress = round(
                sum(weights[frame.status] for frame in frames) / len(frames)
            )
            completed_at = None
            error = next((frame.error for frame in frames if frame.error), None)
            active_statuses = {
                StorylineFrameStatus.QUEUED,
                StorylineFrameStatus.GENERATING,
                StorylineFrameStatus.SAVING,
            }
            active = any(frame.status in active_statuses for frame in frames)
            blocked_pending = {
                frame.frame_id
                for lane in record.plan.lanes
                if not record.references
                and lane.frames[0].status
                in {StorylineFrameStatus.FAILED, StorylineFrameStatus.CANCELLED}
                for frame in lane.frames[1:]
                if frame.status == StorylineFrameStatus.PENDING
            }
            pending = {
                frame.frame_id
                for frame in frames
                if frame.status == StorylineFrameStatus.PENDING
            }
            all_pending_blocked = bool(pending) and pending == blocked_pending
            if terminal == len(frames) or (not active and all_pending_blocked):
                completed_at = now
                if ready == len(frames):
                    status = StorylineStatus.COMPLETED
                elif ready > 0:
                    status = StorylineStatus.PARTIAL
                elif cancelled == len(frames):
                    status = StorylineStatus.CANCELLED
                else:
                    status = StorylineStatus.FAILED
                progress = 100
            elif active:
                status = StorylineStatus.GENERATING
            else:
                status = StorylineStatus.QUEUED
            return record.model_copy(
                update={
                    "status": status,
                    "stage": status.value,
                    "progress": progress,
                    "error": error,
                    "cancel_requested": (
                        False
                        if status == StorylineStatus.COMPLETED
                        else record.cancel_requested
                    ),
                    "completed_at": completed_at,
                    "updated_at": now,
                }
            )

        current = await self.manager.store.get(storyline_id)
        if current is None:
            raise StorylineNotFoundError(storyline_id)
        candidate = recompute(current)
        material_fields = (
            "status",
            "stage",
            "progress",
            "error",
            "cancel_requested",
            "completed_at",
        )
        if all(
            getattr(candidate, field) == getattr(current, field)
            for field in material_fields
        ):
            return current

        return await self.manager.mutate_record(
            storyline_id,
            owner_id=None,
            mutator=recompute,
        )

    @staticmethod
    def _all_frames_ready(record: StorylineRecord) -> bool:
        return bool(record.plan) and all(
            frame.status == StorylineFrameStatus.READY
            for lane in record.plan.lanes
            for frame in lane.frames
        )

    async def _cancel_image_jobs(self, record: StorylineRecord) -> None:
        if record.plan is None:
            return
        for lane in record.plan.lanes:
            for frame in lane.frames:
                if not frame.image_job_id or frame.status in {
                    StorylineFrameStatus.READY,
                    StorylineFrameStatus.FAILED,
                    StorylineFrameStatus.CANCELLED,
                }:
                    continue
                try:
                    await self.image_jobs.cancel(
                        frame.image_job_id,
                        owner_id=record.owner_id,
                    )
                except ImageJobNotFoundError:
                    continue

    async def _mark_cancelled(
        self, storyline_id: str, *, owner_id: str
    ) -> StorylineRecord:
        now = utcnow()

        def cancel(record: StorylineRecord) -> StorylineRecord:
            plan = record.plan
            if plan is not None:

                def cancel_frame(frame: StorylineFrame) -> StorylineFrame:
                    if frame.status == StorylineFrameStatus.READY:
                        return frame
                    payload = frame.model_dump(mode="python")
                    payload.update(
                        {
                            "status": StorylineFrameStatus.CANCELLED,
                            "asset": None,
                            "error": None,
                        }
                    )
                    return StorylineFrame.model_validate(payload)

                plan = self._map_frames(plan, cancel_frame)
            return record.model_copy(
                update={
                    "plan": plan,
                    "status": StorylineStatus.CANCELLED,
                    "stage": StorylineStatus.CANCELLED.value,
                    "progress": 100,
                    "cancel_requested": True,
                    "completed_at": now,
                    "updated_at": now,
                }
            )

        return await self.manager.mutate_record(
            storyline_id,
            owner_id=owner_id,
            mutator=cancel,
        )

    async def _mark_planning_failed(
        self,
        storyline_id: str,
        owner_id: str,
        exc: Exception,
        *,
        expected_revision: int,
    ) -> None:
        now = utcnow()
        error_message = str(exc)[:4000] or exc.__class__.__name__

        def fail(record: StorylineRecord) -> StorylineRecord:
            return record.model_copy(
                update={
                    "status": StorylineStatus.FAILED,
                    "stage": "planning_failed",
                    "progress": 100,
                    "error": error_message,
                    "completed_at": now,
                    "updated_at": now,
                }
            )

        try:
            await self.manager.mutate_record(
                storyline_id,
                owner_id=owner_id,
                mutator=fail,
                expected_revision=expected_revision,
            )
        except Exception:
            logger.exception(
                "Could not persist planning failure for storyline %s", storyline_id
            )

    def _materialize_plan(
        self,
        storyline: Storyline,
        planned: PlannedStoryline,
    ) -> StorylinePlan:
        logical_ids = [str(uuid.uuid4()) for _ in planned.frames]
        lanes: list[StorylineLane] = []
        reference_count = len(storyline.references)
        for model in storyline.settings.models:
            capability = get_image_model_capabilities(
                model,
                provider=settings.MODEL_PROVIDER,
            )
            lane_id = str(uuid.uuid4())
            frames = tuple(
                StorylineFrame(
                    plan_frame_id=logical_ids[index],
                    lane_id=lane_id,
                    order=frame.index,
                    title=frame.purpose[:256],
                    purpose=frame.purpose,
                    prompt=frame.prompt,
                    copy=frame.copy_text,
                )
                for index, frame in enumerate(planned.frames)
            )
            lanes.append(
                StorylineLane(
                    lane_id=lane_id,
                    model=model,
                    label=capability.display_name,
                    capability_disclosure=capability.disclosure,
                    reference_image_limit=capability.max_reference_images,
                    reduced_reference_fidelity=(
                        reference_count > capability.max_reference_images
                    ),
                    frames=frames,
                )
            )
        return StorylinePlan(
            creative_direction=planned.creative_direction,
            lanes=tuple(lanes),
        )

    @staticmethod
    def _reference_to_pipeline(
        reference: StorylineReference,
    ) -> PipelineImageReference:
        return PipelineImageReference(
            blob_name=reference.blob_name,
            container=reference.container,
            content_type=reference.content_type,
            original_filename=reference.original_filename,
        )

    @staticmethod
    async def _build_signed_reference_url(reference: StorylineReference) -> str:
        token, _ = await get_container_sas_token(reference.container)
        base_url = get_blob_container_url(reference.container).rstrip("/")
        blob_url = f"{base_url}/{quote(reference.blob_name, safe='/')}"
        return f"{blob_url}?{token}" if token else blob_url

    @staticmethod
    def _map_frames(
        plan: StorylinePlan,
        transform: Callable[[StorylineFrame], StorylineFrame],
    ) -> StorylinePlan:
        lanes: list[StorylineLane] = []
        for lane in plan.lanes:
            lane_payload = lane.model_dump(mode="python")
            lane_payload["frames"] = tuple(transform(frame) for frame in lane.frames)
            lanes.append(StorylineLane.model_validate(lane_payload))
        plan_payload = plan.model_dump(mode="python")
        plan_payload["lanes"] = tuple(lanes)
        return StorylinePlan.model_validate(plan_payload)

    @staticmethod
    def _find_frame(record: StorylineRecord, frame_id: str) -> StorylineFrame:
        if record.plan is not None:
            for lane in record.plan.lanes:
                for frame in lane.frames:
                    if frame.frame_id == frame_id:
                        return frame
        raise StorylineNotFoundError(frame_id)

    @staticmethod
    def _frame_from_job(
        frame: StorylineFrame,
        job: ImageJob | None,
    ) -> StorylineFrame:
        payload = frame.model_dump(mode="python")
        payload["asset"] = None
        payload["error"] = None
        if job is None:
            payload.update(
                {
                    "status": StorylineFrameStatus.FAILED,
                    "error": "The underlying image job could not be found",
                }
            )
            return StorylineFrame.model_validate(payload)

        output = job.outputs[0] if job.outputs else None
        if output is not None and output.status == ImageJobOutputStatus.READY:
            asset = output.asset
            if asset is not None:
                payload.update(
                    {
                        "status": StorylineFrameStatus.READY,
                        "asset": StorylineFrameAsset.model_validate(asset),
                    }
                )
                return StorylineFrame.model_validate(payload)

        if job.status == ImageJobStatus.QUEUED:
            payload["status"] = StorylineFrameStatus.QUEUED
        elif job.status == ImageJobStatus.GENERATING:
            payload["status"] = StorylineFrameStatus.GENERATING
        elif job.status in {ImageJobStatus.SAVING, ImageJobStatus.ANALYZING}:
            payload["status"] = StorylineFrameStatus.SAVING
        elif job.status in {ImageJobStatus.CANCELLED, ImageJobStatus.CANCEL_REQUESTED}:
            payload["status"] = StorylineFrameStatus.CANCELLED
        elif job.status in {
            ImageJobStatus.FAILED,
            ImageJobStatus.PARTIAL,
            ImageJobStatus.COMPLETED,
        }:
            error = (
                job.error
                or (output.error if output else None)
                or ("The image job completed without a saved frame")
            )
            payload.update(
                {
                    "status": StorylineFrameStatus.FAILED,
                    "error": error[:4000],
                }
            )
        return StorylineFrame.model_validate(payload)
