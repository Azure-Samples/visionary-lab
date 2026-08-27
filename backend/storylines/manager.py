"""Persistence-first storyline lifecycle manager.

This module intentionally does not call language or image models. Future runners can
use ``mutate_record`` to publish planned and generated frame state atomically.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from backend.models.storylines import (
    TERMINAL_STORYLINE_STATUSES,
    Storyline,
    StorylineCreateRequest,
    StorylineFrame,
    StorylineFrameStatus,
    StorylineLane,
    StorylinePlan,
    StorylineRecord,
    StorylineStatus,
)
from backend.storylines.store import (
    StorylineMutator,
    StorylineStore,
    StorylineStoreConflictError,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StorylineNotFoundError(Exception):
    pass


class StorylineConflictError(Exception):
    pass


class StorylineManager:
    """Own storyline validation and atomic aggregate state transitions."""

    def __init__(self, *, store: StorylineStore, retention_seconds: int | None = None):
        self.store = store
        self.retention_seconds = retention_seconds
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        await self.store.start()
        self._started = True

    async def close(self) -> None:
        if not self._started:
            return
        await self.store.close()
        self._started = False

    async def health_check(self) -> None:
        if not self._started:
            raise RuntimeError("Storyline manager is not started")
        await self.store.health_check()

    @staticmethod
    def to_public(record: StorylineRecord) -> Storyline:
        return Storyline.model_validate(record.model_dump(mode="python"))

    async def create(
        self, request: StorylineCreateRequest, *, owner_id: str
    ) -> Storyline:
        canonical_payload = request.model_dump(
            mode="json",
            exclude={"idempotency_key", "client_request_id"},
        )
        canonical_request = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        storyline_id = (
            str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"visionary-lab:storyline:{owner_id}:{request.idempotency_key}",
                )
            )
            if request.idempotency_key
            else str(uuid.uuid4())
        )
        now = utcnow()
        record = StorylineRecord(
            id=storyline_id,
            status=StorylineStatus.DRAFT,
            stage=StorylineStatus.DRAFT.value,
            progress=0,
            title=request.title,
            settings=request.settings,
            references=request.references,
            plan=None,
            owner_id=owner_id,
            client_request_id=request.client_request_id or request.idempotency_key,
            request_hash=request_hash,
            idempotency_key=request.idempotency_key,
            created_at=now,
            updated_at=now,
            ttl=self.retention_seconds,
        )
        persisted, created = await self.store.create(record)
        if not created and persisted.request_hash != request_hash:
            raise StorylineConflictError(
                "The idempotency key was already used for a different storyline"
            )
        return self.to_public(persisted)

    async def get(self, storyline_id: str, *, owner_id: str) -> Storyline:
        record = await self.store.get(storyline_id, owner_id=owner_id)
        if record is None:
            raise StorylineNotFoundError(storyline_id)
        return self.to_public(record)

    async def list_storylines(
        self,
        *,
        owner_id: str,
        limit: int,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> tuple[list[Storyline], int]:
        records, total = await self.store.list_storylines(
            owner_id,
            limit=limit,
            offset=offset,
            statuses=statuses,
        )
        return [self.to_public(record) for record in records], total

    async def mutate_record(
        self,
        storyline_id: str,
        *,
        owner_id: str | None,
        mutator: StorylineMutator,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> StorylineRecord:
        try:
            updated = await self.store.mutate(
                storyline_id,
                mutator,
                owner_id=owner_id,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
        except StorylineStoreConflictError as exc:
            raise StorylineConflictError(str(exc)) from exc
        if updated is None:
            raise StorylineNotFoundError(storyline_id)
        return updated

    async def update_plan(
        self,
        storyline_id: str,
        plan: StorylinePlan,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> Storyline:
        now = utcnow()

        def replace_plan(record: StorylineRecord) -> StorylineRecord:
            recovering_planning_failure = (
                record.status == StorylineStatus.FAILED
                and record.stage == "planning_failed"
                and record.plan is None
            )
            if (
                record.status
                not in {
                    StorylineStatus.DRAFT,
                    StorylineStatus.PLANNED,
                }
                and not recovering_planning_failure
            ):
                raise StorylineConflictError(
                    "A storyline plan can only change before generation starts"
                )
            try:
                frame_count = len(plan.lanes[0].frames)
                if not 2 <= frame_count <= 10:
                    raise ValueError(
                        "A storyline plan must contain between 2 and 10 frames"
                    )
                settings = record.settings.model_copy(
                    update={"frame_count": frame_count}
                )
                plan.validate_against(settings)
            except ValueError as exc:
                raise StorylineConflictError(str(exc)) from exc
            if record.plan is not None:
                if plan.plan_id != record.plan.plan_id:
                    raise StorylineConflictError(
                        "Plan updates must preserve the existing plan_id"
                    )
                if plan.version <= record.plan.version:
                    raise StorylineConflictError(
                        "Plan updates must increment the plan version"
                    )
                persisted_plan = self._sanitize_reviewed_plan(record.plan, plan)
            else:
                persisted_plan = self._strip_execution_state(plan)
            return record.model_copy(
                update={
                    "plan": persisted_plan,
                    "settings": settings,
                    "status": StorylineStatus.PLANNED,
                    "stage": StorylineStatus.PLANNED.value,
                    "progress": 0,
                    "error": None,
                    "cancel_requested": False,
                    "completed_at": None,
                    "updated_at": now,
                }
            )

        updated = await self.mutate_record(
            storyline_id,
            owner_id=owner_id,
            mutator=replace_plan,
            expected_revision=expected_revision,
            expected_etag=expected_etag,
        )
        return self.to_public(updated)

    @staticmethod
    def _strip_execution_state(plan: StorylinePlan) -> StorylinePlan:
        """Ensure even an initial plan cannot smuggle generated execution state."""

        lanes: list[StorylineLane] = []
        for lane in plan.lanes:
            frames = tuple(
                StorylineFrame(
                    frame_id=frame.frame_id,
                    plan_frame_id=frame.plan_frame_id,
                    lane_id=lane.lane_id,
                    order=frame.order,
                    title=frame.title,
                    purpose=frame.purpose,
                    prompt=frame.prompt,
                    copy=frame.copy_text,
                )
                for frame in lane.frames
            )
            lanes.append(lane.model_copy(update={"frames": frames}))
        return plan.model_copy(update={"lanes": tuple(lanes)})

    @staticmethod
    def _sanitize_reviewed_plan(
        existing: StorylinePlan,
        submitted: StorylinePlan,
    ) -> StorylinePlan:
        """Persist creative edits while retaining server-owned lane execution data."""

        logical_frames = submitted.lanes[0].frames
        lanes: list[StorylineLane] = []
        for existing_lane in existing.lanes:
            old_by_logical_id = {
                frame.plan_frame_id: frame for frame in existing_lane.frames
            }
            frames: list[StorylineFrame] = []
            for logical in logical_frames:
                old = old_by_logical_id.get(logical.plan_frame_id)
                frames.append(
                    StorylineFrame(
                        frame_id=old.frame_id if old is not None else str(uuid.uuid4()),
                        plan_frame_id=logical.plan_frame_id,
                        lane_id=existing_lane.lane_id,
                        order=logical.order,
                        title=logical.title,
                        purpose=logical.purpose,
                        prompt=logical.prompt,
                        copy=logical.copy_text,
                    )
                )
            lanes.append(existing_lane.model_copy(update={"frames": tuple(frames)}))
        return StorylinePlan(
            plan_id=existing.plan_id,
            version=existing.version + 1,
            creative_direction=submitted.creative_direction,
            lanes=tuple(lanes),
        )

    async def cancel(
        self,
        storyline_id: str,
        *,
        owner_id: str,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> Storyline:
        now = utcnow()

        def cancel_storyline(record: StorylineRecord) -> StorylineRecord:
            if record.status in TERMINAL_STORYLINE_STATUSES:
                return record
            plan = (
                self._map_frames(record.plan, self._cancel_frame)
                if record.plan is not None
                else None
            )
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

        updated = await self.mutate_record(
            storyline_id,
            owner_id=owner_id,
            mutator=cancel_storyline,
            expected_revision=expected_revision,
            expected_etag=expected_etag,
        )
        return self.to_public(updated)

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
        return await self._reset_frame(
            storyline_id,
            frame_id,
            owner_id=owner_id,
            allowed_statuses={
                StorylineFrameStatus.FAILED,
                StorylineFrameStatus.CANCELLED,
            },
            stage="frame_retry_requested",
            expected_revision=expected_revision,
            expected_etag=expected_etag,
            prompt=prompt,
            copy_text=copy_text,
        )

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
        return await self._reset_frame(
            storyline_id,
            frame_id,
            owner_id=owner_id,
            allowed_statuses={
                StorylineFrameStatus.PENDING,
                StorylineFrameStatus.QUEUED,
                StorylineFrameStatus.READY,
                StorylineFrameStatus.FAILED,
                StorylineFrameStatus.CANCELLED,
            },
            stage="frame_regeneration_requested",
            expected_revision=expected_revision,
            expected_etag=expected_etag,
            prompt=prompt,
            copy_text=copy_text,
        )

    async def _reset_frame(
        self,
        storyline_id: str,
        frame_id: str,
        *,
        owner_id: str,
        allowed_statuses: set[StorylineFrameStatus],
        stage: str,
        expected_revision: int | None,
        expected_etag: str | None,
        prompt: str | None,
        copy_text: str | None,
    ) -> Storyline:
        now = utcnow()

        def reset(record: StorylineRecord) -> StorylineRecord:
            if record.plan is None:
                raise StorylineConflictError("The storyline does not have a plan")
            target = next(
                (
                    frame
                    for lane in record.plan.lanes
                    for frame in lane.frames
                    if frame.frame_id == frame_id
                ),
                None,
            )
            if target is None:
                raise StorylineNotFoundError(frame_id)
            if target.status not in allowed_statuses:
                raise StorylineConflictError(
                    f"Frame {frame_id} cannot be reset from {target.status.value}"
                )
            prompt_changed = prompt is not None and prompt != target.prompt
            affected_lane_ids = (
                {lane.lane_id for lane in record.plan.lanes}
                if prompt_changed
                else {target.lane_id}
            )

            def reset_candidate(frame: StorylineFrame) -> StorylineFrame:
                is_target = frame.frame_id == frame_id
                shares_logical_frame = frame.plan_frame_id == target.plan_frame_id
                is_anchor_dependent = (
                    not record.references
                    and target.order == 1
                    and frame.lane_id in affected_lane_ids
                    and frame.order > 1
                )
                resets_execution = (
                    is_target
                    or (shares_logical_frame and prompt_changed)
                    or is_anchor_dependent
                )
                updates_logical_content = shares_logical_frame and (
                    prompt is not None or copy_text is not None
                )
                if not resets_execution and not updates_logical_content:
                    return frame
                payload = frame.model_dump(mode="python")
                if resets_execution:
                    payload.update(
                        {
                            "status": StorylineFrameStatus.PENDING,
                            "attempt": (
                                frame.attempt + 1
                                if is_target
                                or frame.status != StorylineFrameStatus.PENDING
                                or frame.image_job_id is not None
                                else frame.attempt
                            ),
                            "asset": None,
                            "image_job_id": None,
                            "error": None,
                        }
                    )
                if shares_logical_frame and prompt is not None:
                    payload["prompt"] = prompt
                if shares_logical_frame and copy_text is not None:
                    payload["copy_text"] = copy_text
                return StorylineFrame.model_validate(payload)

            plan = self._map_frames(record.plan, reset_candidate)
            ready_count = sum(
                frame.status == StorylineFrameStatus.READY
                for lane in plan.lanes
                for frame in lane.frames
            )
            total = sum(len(lane.frames) for lane in plan.lanes)
            progress = round(100 * ready_count / total) if total else 0
            return record.model_copy(
                update={
                    "plan": plan,
                    "status": StorylineStatus.QUEUED,
                    "stage": stage,
                    "progress": min(progress, 99),
                    "error": None,
                    "cancel_requested": False,
                    "completed_at": None,
                    "updated_at": now,
                }
            )

        updated = await self.mutate_record(
            storyline_id,
            owner_id=owner_id,
            mutator=reset,
            expected_revision=expected_revision,
            expected_etag=expected_etag,
        )
        return self.to_public(updated)

    @staticmethod
    def _map_frames(
        plan: StorylinePlan,
        transform,
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
    def _cancel_frame(frame: StorylineFrame) -> StorylineFrame:
        if frame.status == StorylineFrameStatus.READY:
            return frame
        payload = frame.model_dump(mode="python")
        payload.update(
            {
                "status": StorylineFrameStatus.CANCELLED,
                "asset": None,
                "image_job_id": None,
            }
        )
        return StorylineFrame.model_validate(payload)
