"""Lifecycle manager for durable, cancellable image-generation jobs."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from fastapi import HTTPException

from backend.jobs.queue import ImageJobQueue, ImageJobQueueMessage
from backend.jobs.store import ImageJobStore, image_job_partition
from backend.models.image_jobs import (
    ACTIVE_IMAGE_JOB_STATUSES,
    TERMINAL_IMAGE_JOB_STATUSES,
    ImageJob,
    ImageJobAnalysisStatus,
    ImageJobCreateRequest,
    ImageJobOutput,
    ImageJobOutputStatus,
    ImageJobRecord,
    ImageJobStatus,
)
from backend.models.images import ImagePipelineRequest, ImageSaveResponse, PipelineAction

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImageJobNotFoundError(Exception):
    pass


class ImageJobConflictError(Exception):
    pass


@dataclass(slots=True)
class ImageJobProgress:
    status: ImageJobStatus
    progress: int
    completed_images: int | None = None
    failed_images: int | None = None
    output_index: int | None = None
    output_status: ImageJobOutputStatus | None = None
    asset: dict[str, Any] | None = None
    error: str | None = None
    analysis_status: ImageJobAnalysisStatus | None = None


ProgressReporter = Callable[[ImageJobProgress], Awaitable[None]]


class ImagePipelineRunner(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def __call__(
        self,
        request: ImagePipelineRequest,
        report_progress: ProgressReporter,
    ) -> ImageSaveResponse: ...


class DefaultImagePipelineRunner:
    """Bridge the durable worker to the existing native-async pipeline service."""

    def __init__(self) -> None:
        self._storage = None
        self._cosmos = None
        self._pipeline = None

    async def start(self) -> None:
        if self._pipeline is not None:
            return
        from backend.core.azure_storage import AzureBlobStorageService
        from backend.core.config import settings
        from backend.core.cosmos_async import AsyncCosmosAssetService
        from backend.core.image_pipeline import ImagePipelineService

        self._storage = AzureBlobStorageService()
        self._pipeline = ImagePipelineService()
        if settings.AZURE_COSMOS_DB_ENDPOINT:
            self._cosmos = AsyncCosmosAssetService(
                endpoint=settings.AZURE_COSMOS_DB_ENDPOINT,
                database_id=settings.AZURE_COSMOS_DB_ID,
                container_id=settings.AZURE_COSMOS_CONTAINER_ID,
            )
            await self._cosmos.start()

    async def close(self) -> None:
        pipeline, self._pipeline = self._pipeline, None
        storage, self._storage = self._storage, None
        cosmos, self._cosmos = self._cosmos, None

        if pipeline is not None:
            close = getattr(pipeline, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
        if storage is not None:
            close = getattr(storage, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result
        if cosmos is not None:
            close = getattr(cosmos, "close", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result

    async def __call__(
        self,
        request: ImagePipelineRequest,
        report_progress: ProgressReporter,
    ) -> ImageSaveResponse:
        if self._pipeline is None or self._storage is None:
            await self.start()
        assert self._pipeline is not None
        assert self._storage is not None

        await report_progress(
            ImageJobProgress(
                status=ImageJobStatus.GENERATING,
                progress=10,
                output_status=ImageJobOutputStatus.GENERATING,
            )
        )

        async def pipeline_progress(stage: str, details: dict[str, object]) -> None:
            total = max(1, int(details.get("total") or request.n))
            completed = max(0, int(details.get("completed") or 0))
            phase_complete = details.get("status") == "completed"
            if stage in {"generating", "editing"}:
                job_status = ImageJobStatus.GENERATING
                progress = 45 if phase_complete else 10
                completed_images = None
            elif stage == "saving":
                job_status = ImageJobStatus.SAVING
                progress = 50 + round(35 * min(completed, total) / total)
                completed_images = completed
            elif stage == "analyzing":
                job_status = ImageJobStatus.ANALYZING
                progress = 88 + round(10 * min(completed, total) / total)
                completed_images = total
            else:
                return
            failed = details.get("failed")
            output_index = details.get("image_index")
            output_status = None
            analysis_status = None
            asset = details.get("asset")
            error = details.get("error")
            if stage == "saving":
                output_status = (
                    ImageJobOutputStatus.FAILED
                    if error
                    else ImageJobOutputStatus.READY
                    if asset is not None
                    else ImageJobOutputStatus.SAVING
                )
            elif stage == "analyzing":
                if details.get("status") == "completed":
                    analysis_status = None
                elif details.get("status") == "in_progress":
                    analysis_status = (
                        ImageJobAnalysisStatus.FAILED
                        if details.get("success") is False
                        else ImageJobAnalysisStatus.COMPLETED
                    )
                else:
                    analysis_status = ImageJobAnalysisStatus.ANALYZING
            await report_progress(
                ImageJobProgress(
                    status=job_status,
                    progress=progress,
                    completed_images=completed_images,
                    failed_images=(
                        int(failed)
                        if failed is not None and stage == "saving"
                        else None
                    ),
                    output_index=(
                        int(output_index) if output_index is not None else None
                    ),
                    output_status=output_status,
                    asset=asset if isinstance(asset, dict) else None,
                    error=str(error) if error else None,
                    analysis_status=analysis_status,
                )
            )

        response = await self._pipeline.process_pipeline(
            request,
            azure_storage_service=self._storage,
            cosmos_service=self._cosmos,
            progress_callback=pipeline_progress,
        )
        if response.save is None:
            raise RuntimeError("Image pipeline completed without durable saved images")
        return response.save


class ImageJobManager:
    def __init__(
        self,
        *,
        store: ImageJobStore,
        queue: ImageJobQueue,
        runner: ImagePipelineRunner,
        concurrency: int = 2,
        poll_interval: float = 1.0,
        visibility_timeout: int = 600,
        cancellation_poll_interval: float = 2.0,
        heartbeat_interval: float | None = None,
        reconcile_interval: float = 5.0,
        max_attempts: int = 3,
        rate_limit_max_attempts: int = 8,
        rate_limit_base_delay: int = 30,
        rate_limit_max_delay: int = 300,
        rate_limit_jitter: int = 15,
        retention_seconds: int = 60 * 60 * 24 * 30,
    ) -> None:
        if concurrency < 1:
            raise ValueError("Image job concurrency must be at least one")
        self.store = store
        self.queue = queue
        self.runner = runner
        self.concurrency = concurrency
        self.poll_interval = poll_interval
        self.visibility_timeout = visibility_timeout
        self.cancellation_poll_interval = min(
            cancellation_poll_interval, max(0.25, visibility_timeout / 3)
        )
        self.heartbeat_interval = heartbeat_interval or max(5.0, visibility_timeout / 3)
        self.heartbeat_interval = min(
            self.heartbeat_interval, max(1.0, visibility_timeout * 0.8)
        )
        self.reconcile_interval = max(0.25, reconcile_interval)
        self.max_attempts = max(1, max_attempts)
        self.rate_limit_max_attempts = max(
            self.max_attempts, rate_limit_max_attempts
        )
        self.rate_limit_base_delay = max(1, rate_limit_base_delay)
        self.rate_limit_max_delay = max(
            self.rate_limit_base_delay, rate_limit_max_delay
        )
        self.rate_limit_jitter = max(0, rate_limit_jitter)
        self.retention_seconds = max(60, retention_seconds)
        self._workers: list[asyncio.Task[None]] = []
        self._dispatcher: asyncio.Task[None] | None = None
        self._running_jobs: dict[str, asyncio.Task[ImageSaveResponse]] = {}
        self._stopping = False
        self._started = False
        self._runner_started = False

    async def start(self, *, run_workers: bool = True) -> None:
        if self._started:
            return
        await self.store.start()
        try:
            await self.queue.start()
            if run_workers:
                start_runner = getattr(self.runner, "start", None)
                if start_runner is not None:
                    result = start_runner()
                    if inspect.isawaitable(result):
                        await result
                self._runner_started = True
        except BaseException:
            await self.queue.close()
            await self.store.close()
            raise
        self._stopping = False
        self._workers = (
            [
                asyncio.create_task(
                    self._worker_loop(index), name=f"image-job-worker-{index}"
                )
                for index in range(self.concurrency)
            ]
            if run_workers
            else []
        )
        self._dispatcher = asyncio.create_task(
            self._dispatch_loop(), name="image-job-dispatcher"
        )
        self._started = True

    async def close(self) -> None:
        if not self._started:
            return
        self._stopping = True
        if self._dispatcher is not None:
            self._dispatcher.cancel()
        for worker in self._workers:
            worker.cancel()
        tasks = [*self._workers]
        if self._dispatcher is not None:
            tasks.append(self._dispatcher)
        await asyncio.gather(*tasks, return_exceptions=True)
        self._workers.clear()
        self._dispatcher = None
        running = list(self._running_jobs.values())
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        self._running_jobs.clear()
        if self._runner_started:
            close_runner = getattr(self.runner, "close", None)
            if close_runner is not None:
                result = close_runner()
                if inspect.isawaitable(result):
                    await result
            self._runner_started = False
        await self.queue.close()
        await self.store.close()
        self._started = False

    @staticmethod
    def to_public(record: ImageJobRecord) -> ImageJob:
        return ImageJob.model_validate(record.model_dump(mode="python"))

    async def health_check(self) -> dict[str, str]:
        if not self._started:
            raise RuntimeError("Image job manager is not started")
        await asyncio.gather(
            self.store.health_check(),
            self.queue.health_check(),
        )
        return {"store": "ok", "queue": "ok"}

    async def submit(
        self,
        request: ImageJobCreateRequest,
        *,
        owner_id: str,
        parent_job_id: str | None = None,
        allow_durable_edit: bool = False,
    ) -> ImageJob:
        if request.request.action == PipelineAction.EDIT and not allow_durable_edit:
            raise ImageJobConflictError(
                "Durable edit jobs may only be submitted by a trusted server workflow"
            )
        if request.request.source_image_blobs:
            from backend.core.config import settings

            if any(
                reference.container != settings.AZURE_BLOB_IMAGE_CONTAINER
                for reference in request.request.source_image_blobs
            ):
                raise ImageJobConflictError(
                    "Durable image-job sources must use the configured image container"
                )
        canonical_request = json.dumps(
            request.request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        if request.idempotency_key:
            job_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"visionary-lab:image-job:{owner_id}:{request.idempotency_key}",
                )
            )
        else:
            job_id = str(uuid.uuid4())

        pipeline_request = request.request.model_copy(deep=True)
        metadata = dict(pipeline_request.metadata or {})
        metadata["image_job_id"] = job_id
        pipeline_request.metadata = metadata
        save_metadata = dict(pipeline_request.save_options.metadata or {})
        save_metadata["image_job_id"] = job_id
        pipeline_request.save_options.metadata = save_metadata

        now = utcnow()
        record = ImageJobRecord(
            id=job_id,
            storyline_id=(
                str(metadata["storyline_id"])
                if metadata.get("storyline_id")
                else None
            ),
            status=ImageJobStatus.QUEUED,
            stage=ImageJobStatus.QUEUED.value,
            progress=0,
            action=pipeline_request.action,
            prompt=pipeline_request.prompt,
            model=pipeline_request.model,
            size=pipeline_request.size,
            folder_path=pipeline_request.save_options.folder_path,
            analysis_enabled=pipeline_request.analysis_options.enabled,
            requested_images=pipeline_request.n,
            created_at=now,
            updated_at=now,
            parent_job_id=parent_job_id,
            owner_id=owner_id,
            media_type=image_job_partition(job_id),
            pipeline_request=pipeline_request.model_dump(mode="json"),
            client_request_id=request.client_request_id or request.idempotency_key,
            request_hash=request_hash,
            outputs=[
                ImageJobOutput(
                    index=index,
                    analysis_status=(
                        ImageJobAnalysisStatus.PENDING
                        if pipeline_request.analysis_options.enabled
                        else ImageJobAnalysisStatus.NOT_REQUESTED
                    ),
                )
                for index in range(1, pipeline_request.n + 1)
            ],
            ttl=self.retention_seconds,
        )
        persisted, created = await self.store.create(record)
        if not created and persisted.request_hash != request_hash:
            raise ImageJobConflictError(
                "The idempotency key was already used for a different image request"
            )
        if (
            persisted.status == ImageJobStatus.QUEUED
            and persisted.dispatched_at is None
        ):
            persisted = await self._dispatch_job(persisted)
        return self.to_public(persisted)

    async def _dispatch_job(self, job: ImageJobRecord) -> ImageJobRecord:
        await self.queue.enqueue(job.id)
        dispatched_at = utcnow()

        def mark_dispatched(record: ImageJobRecord) -> ImageJobRecord | None:
            if record.status != ImageJobStatus.QUEUED or record.cancel_requested:
                return None
            record.dispatched_at = dispatched_at
            record.updated_at = dispatched_at
            return record

        return await self.store.mutate(job.id, mark_dispatched) or job

    async def _dispatch_loop(self) -> None:
        while True:
            try:
                pending = await self.store.list_pending_dispatch()
                for job in pending:
                    try:
                        await self._dispatch_job(job)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception(
                            "Failed to dispatch image job %s; reconciliation will retry",
                            job.id,
                        )
                await asyncio.sleep(self.reconcile_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Image job dispatch reconciliation failed")
                await asyncio.sleep(self.reconcile_interval)

    async def get(self, job_id: str, *, owner_id: str) -> ImageJob:
        record = await self.store.get(job_id, owner_id=owner_id)
        if record is None:
            raise ImageJobNotFoundError(job_id)
        return self.to_public(record)

    async def list_jobs(
        self,
        *,
        owner_id: str,
        limit: int,
        statuses: set[ImageJobStatus] | None = None,
    ) -> tuple[list[ImageJob], int]:
        records, total = await self.store.list_jobs(owner_id, limit, statuses)
        return [self.to_public(record) for record in records], total

    async def cancel(self, job_id: str, *, owner_id: str) -> ImageJob:
        now = utcnow()

        def request_cancel(job: ImageJobRecord) -> ImageJobRecord:
            if job.status in TERMINAL_IMAGE_JOB_STATUSES:
                return job
            job.cancel_requested = True
            if job.status == ImageJobStatus.QUEUED:
                job.status = ImageJobStatus.CANCELLED
                job.stage = ImageJobStatus.CANCELLED.value
                job.completed_at = now
                for output in job.outputs:
                    output.status = ImageJobOutputStatus.CANCELLED
                    output.progress = 100
            else:
                job.status = ImageJobStatus.CANCEL_REQUESTED
                job.stage = ImageJobStatus.CANCEL_REQUESTED.value
            job.updated_at = now
            return job

        updated = await self.store.mutate(job_id, request_cancel, owner_id=owner_id)
        if updated is None:
            raise ImageJobNotFoundError(job_id)
        running = self._running_jobs.get(job_id)
        if running is not None and not running.done():
            running.cancel()
        return self.to_public(updated)

    async def retry(self, job_id: str, *, owner_id: str) -> ImageJob:
        existing = await self.store.get(job_id, owner_id=owner_id)
        if existing is None:
            raise ImageJobNotFoundError(job_id)
        if existing.status not in {
            ImageJobStatus.FAILED,
            ImageJobStatus.CANCELLED,
            ImageJobStatus.PARTIAL,
        }:
            raise ImageJobConflictError(
                "Only failed or cancelled image jobs can be retried"
            )
        retry_request = ImagePipelineRequest.model_validate(existing.pipeline_request)
        remaining = max(1, existing.requested_images - existing.completed_images)
        retry_request.n = remaining
        payload = ImageJobCreateRequest(
            request=retry_request,
            idempotency_key=f"retry:{existing.id}",
            client_request_id=f"retry:{existing.id}",
        )
        return await self.submit(payload, owner_id=owner_id, parent_job_id=job_id)

    async def _worker_loop(self, index: int) -> None:
        worker_id = f"{uuid.uuid4()}:{index}"
        while True:
            try:
                message = await self.queue.receive()
                if message is None:
                    await asyncio.sleep(self.poll_interval)
                    continue
                await self._handle_message(message, worker_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Image job worker %s failed while polling", worker_id)
                await asyncio.sleep(self.poll_interval)

    async def _handle_message(
        self, message: ImageJobQueueMessage, worker_id: str
    ) -> None:
        existing = await self.store.get(message.job_id)
        if existing is None or existing.status in TERMINAL_IMAGE_JOB_STATUSES:
            await self.queue.delete(message)
            return
        if (
            existing.cancel_requested
            or existing.status == ImageJobStatus.CANCEL_REQUESTED
        ):
            await self._mark_cancelled(message.job_id)
            await self.queue.delete(message)
            return

        claimed = await self._claim(message.job_id, worker_id)
        if claimed is None:
            await self.queue.release(message, delay_seconds=2)
            return

        if claimed.attempt > self.rate_limit_max_attempts:
            reason = (
                "Image job exceeded the maximum of "
                f"{self.rate_limit_max_attempts} worker attempts"
            )
            await self._mark_failed(
                claimed.id,
                worker_id,
                RuntimeError(reason),
            )
            await self.queue.dead_letter(message, reason)
            return

        async def report_progress(update: ImageJobProgress) -> None:
            try:
                await self._record_progress(
                    claimed.id,
                    worker_id,
                    update,
                )
            except Exception:
                # User-visible progress is best-effort. Completion/cancellation
                # still go through the durable lease-checked terminal writes.
                logger.exception(
                    "Could not persist progress for image job %s", claimed.id
                )

        pipeline_request = ImagePipelineRequest.model_validate(claimed.pipeline_request)
        pipeline_task = asyncio.create_task(
            self.runner(pipeline_request, report_progress),
            name=f"image-pipeline-{claimed.id}",
        )
        self._running_jobs[claimed.id] = pipeline_task
        last_heartbeat = asyncio.get_running_loop().time()

        try:
            while True:
                done, _ = await asyncio.wait(
                    {pipeline_task},
                    timeout=self.cancellation_poll_interval,
                )
                if done:
                    break
                try:
                    latest = await self.store.get(claimed.id)
                    if latest is None:
                        await self._cancel_and_wait(pipeline_task)
                        await self.queue.delete(message)
                        return
                    if (
                        latest.cancel_requested
                        or latest.status == ImageJobStatus.CANCEL_REQUESTED
                    ):
                        await self._cancel_and_wait(pipeline_task)
                        await self._mark_cancelled(claimed.id, worker_id=worker_id)
                        await self.queue.delete(message)
                        return

                    now_monotonic = asyncio.get_running_loop().time()
                    if now_monotonic - last_heartbeat >= self.heartbeat_interval:
                        await self.queue.renew(message)
                        await self._renew_lease(claimed.id, worker_id)
                        last_heartbeat = now_monotonic
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Image job %s lost its coordination heartbeat; returning it for recovery",
                        claimed.id,
                    )
                    await self._cancel_and_wait(pipeline_task)
                    await self._release_for_recovery(message, claimed.id, worker_id)
                    return

            if pipeline_task.cancelled():
                latest = await self.store.get(claimed.id)
                if latest is not None and latest.cancel_requested:
                    await self._mark_cancelled(claimed.id, worker_id=worker_id)
                    await self.queue.delete(message)
                    return
                raise RuntimeError(
                    "Image pipeline was cancelled without a job cancellation"
                )

            result = pipeline_task.result()

            # Close the narrow race where cancellation is persisted at the same
            # moment the provider request completes.
            latest = await self.store.get(claimed.id)
            if latest is not None and (
                latest.cancel_requested
                or latest.status == ImageJobStatus.CANCEL_REQUESTED
            ):
                await self._mark_cancelled(claimed.id, worker_id=worker_id)
                await self.queue.delete(message)
                return

            updated = await self._mark_completed(claimed.id, worker_id, result)
            if updated is None:
                latest = await self.store.get(claimed.id)
                if latest is not None and latest.cancel_requested:
                    await self._mark_cancelled(claimed.id, worker_id=worker_id)
                    await self.queue.delete(message)
                else:
                    await self.queue.release(message, delay_seconds=2)
                return
            await self.queue.delete(message)
        except asyncio.CancelledError:
            await self._cancel_and_wait(pipeline_task)
            if self._stopping:
                await self._release_for_recovery(message, claimed.id, worker_id)
            raise
        except Exception as exc:
            await self._cancel_and_wait(pipeline_task)
            latest = await self.store.get(claimed.id)
            if latest is not None and latest.cancel_requested:
                await self._mark_cancelled(claimed.id, worker_id=worker_id)
                await self.queue.delete(message)
                return
            rate_limited = self._is_rate_limit_failure(exc)
            attempt_limit = (
                self.rate_limit_max_attempts if rate_limited else self.max_attempts
            )
            if self._is_transient_failure(exc) and claimed.attempt < attempt_limit:
                delay = (
                    self._rate_limit_retry_delay(
                        exc,
                        job_id=claimed.id,
                        attempt=claimed.attempt,
                    )
                    if rate_limited
                    else min(60, 2 ** max(1, claimed.attempt))
                )
                logger.warning(
                    "Transient failure for image job %s (attempt %s/%s); retrying in %ss: %s",
                    claimed.id,
                    claimed.attempt,
                    attempt_limit,
                    delay,
                    exc,
                )
                await self._release_for_recovery(
                    message, claimed.id, worker_id, delay_seconds=delay
                )
                return
            try:
                await self._mark_failed(claimed.id, worker_id, exc)
                await self.queue.dead_letter(message, str(exc))
            except Exception:
                logger.exception(
                    "Failed to persist terminal failure for image job %s; releasing it",
                    claimed.id,
                )
                await self._release_for_recovery(message, claimed.id, worker_id)
        finally:
            self._running_jobs.pop(claimed.id, None)

    @staticmethod
    async def _cancel_and_wait(task: asyncio.Task[Any]) -> None:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _release_for_recovery(
        self,
        message: ImageJobQueueMessage,
        job_id: str,
        worker_id: str,
        delay_seconds: int = 2,
    ) -> None:
        try:
            await self._return_to_queue(job_id, worker_id)
        except Exception:
            logger.exception("Could not reset image job %s to queued", job_id)
        await self.queue.release(message, delay_seconds=delay_seconds)

    @staticmethod
    def _is_transient_failure(exc: Exception) -> bool:
        if isinstance(exc, HTTPException):
            return exc.status_code in {408, 409, 425, 429} or exc.status_code >= 500
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code in {408, 409, 425, 429} or status_code >= 500
        return isinstance(exc, (TimeoutError, ConnectionError))

    @staticmethod
    def _is_rate_limit_failure(exc: Exception) -> bool:
        return getattr(exc, "status_code", None) == 429

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> int | None:
        value = getattr(exc, "retry_after_seconds", None)
        if value is None and isinstance(exc, HTTPException) and exc.headers:
            value = exc.headers.get("Retry-After") or exc.headers.get("retry-after")
        try:
            return max(0, int(float(value))) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _rate_limit_retry_delay(
        self,
        exc: Exception,
        *,
        job_id: str,
        attempt: int,
    ) -> int:
        explicit_delay = self._retry_after_seconds(exc)
        if explicit_delay is not None:
            # Provider guidance takes precedence over the fallback cap. Retrying
            # earlier than Retry-After would only extend the throttling window.
            return max(1, explicit_delay)

        exponent = max(0, attempt - 1)
        base_delay = min(
            self.rate_limit_max_delay,
            self.rate_limit_base_delay * (2**exponent),
        )
        available_jitter = min(
            self.rate_limit_jitter,
            self.rate_limit_max_delay - base_delay,
        )
        if available_jitter <= 0:
            return base_delay
        digest = hashlib.sha256(f"{job_id}:{attempt}".encode("utf-8")).digest()
        jitter = int.from_bytes(digest[:4], "big") % (available_jitter + 1)
        return base_delay + jitter

    async def _claim(self, job_id: str, worker_id: str) -> ImageJobRecord | None:
        now = utcnow()
        lease_expires = now + timedelta(seconds=self.visibility_timeout)

        def claim(job: ImageJobRecord) -> ImageJobRecord | None:
            stale = (
                job.status in ACTIVE_IMAGE_JOB_STATUSES
                and job.lease_expires_at is not None
                and job.lease_expires_at <= now
            )
            if job.status != ImageJobStatus.QUEUED and not stale:
                return None
            if job.cancel_requested:
                return None
            job.status = ImageJobStatus.GENERATING
            job.stage = ImageJobStatus.GENERATING.value
            job.progress = max(job.progress, 5)
            job.started_at = job.started_at or now
            job.updated_at = now
            job.lease_owner = worker_id
            job.lease_expires_at = lease_expires
            job.delivery_count += 1
            job.attempt = job.delivery_count
            for output in job.outputs:
                if output.status not in {
                    ImageJobOutputStatus.READY,
                    ImageJobOutputStatus.FAILED,
                    ImageJobOutputStatus.CANCELLED,
                }:
                    output.status = ImageJobOutputStatus.GENERATING
                    output.progress = max(output.progress, 5)
            return job

        return await self.store.mutate(job_id, claim)

    async def _renew_lease(self, job_id: str, worker_id: str) -> None:
        now = utcnow()

        def renew(job: ImageJobRecord) -> ImageJobRecord | None:
            if (
                job.lease_owner != worker_id
                or job.status not in ACTIVE_IMAGE_JOB_STATUSES
            ):
                return None
            job.lease_expires_at = now + timedelta(seconds=self.visibility_timeout)
            job.updated_at = now
            return job

        await self.store.mutate(job_id, renew)

    async def _record_progress(
        self,
        job_id: str,
        worker_id: str,
        progress_update: ImageJobProgress,
    ) -> None:
        if progress_update.status not in ACTIVE_IMAGE_JOB_STATUSES:
            raise ValueError(
                f"Invalid active progress status: {progress_update.status}"
            )
        now = utcnow()

        def mutate(job: ImageJobRecord) -> ImageJobRecord | None:
            if job.lease_owner != worker_id or job.cancel_requested:
                return None
            job.status = progress_update.status
            job.stage = progress_update.status.value
            job.progress = max(job.progress, min(99, max(0, progress_update.progress)))
            if progress_update.completed_images is not None:
                job.completed_images = max(
                    job.completed_images, progress_update.completed_images
                )
            if progress_update.failed_images is not None:
                job.failed_images = max(
                    job.failed_images, progress_update.failed_images
                )

            targets = (
                [
                    output
                    for output in job.outputs
                    if output.index == progress_update.output_index
                ]
                if progress_update.output_index is not None
                else [
                    output
                    for output in job.outputs
                    if output.status == ImageJobOutputStatus.READY
                ]
                if progress_update.analysis_status is not None
                else [
                    output
                    for output in job.outputs
                    if output.status
                    not in {
                        ImageJobOutputStatus.READY,
                        ImageJobOutputStatus.FAILED,
                        ImageJobOutputStatus.CANCELLED,
                    }
                ]
            )
            for output in targets:
                if progress_update.output_status is not None:
                    output.status = progress_update.output_status
                output.progress = max(
                    output.progress,
                    100
                    if progress_update.output_status
                    in {
                        ImageJobOutputStatus.READY,
                        ImageJobOutputStatus.FAILED,
                        ImageJobOutputStatus.CANCELLED,
                    }
                    else min(99, max(0, progress_update.progress)),
                )
                if progress_update.asset is not None:
                    output.asset = progress_update.asset
                    output.error = None
                if progress_update.error:
                    output.error = progress_update.error
                if progress_update.analysis_status is not None:
                    output.analysis_status = progress_update.analysis_status
            job.updated_at = now
            return job

        await self.store.mutate(job_id, mutate)

    async def _mark_completed(
        self,
        job_id: str,
        worker_id: str,
        result: ImageSaveResponse,
    ) -> ImageJobRecord | None:
        now = utcnow()

        def complete(job: ImageJobRecord) -> ImageJobRecord | None:
            if job.lease_owner != worker_id or job.cancel_requested:
                return None
            job.failed_images = max(0, job.requested_images - result.total_saved)
            job.status = (
                ImageJobStatus.PARTIAL
                if job.failed_images > 0
                else ImageJobStatus.COMPLETED
            )
            job.stage = job.status.value
            job.progress = 100
            job.completed_images = result.total_saved
            job.result = result
            job.error = (
                f"{job.failed_images} image output(s) did not complete"
                if job.failed_images
                else None
            )
            for fallback_index, asset in enumerate(result.saved_images, start=1):
                asset_data = asset.model_dump(mode="json", exclude_none=True)
                raw_index = asset_data.get("original_index", fallback_index)
                try:
                    output_index = int(raw_index)
                except (TypeError, ValueError):
                    output_index = fallback_index
                output = next(
                    (item for item in job.outputs if item.index == output_index),
                    None,
                )
                if output is not None:
                    output.status = ImageJobOutputStatus.READY
                    output.progress = 100
                    output.asset = asset_data
                    output.error = None
                    if job.analysis_enabled:
                        if not result.analyzed:
                            output.analysis_status = ImageJobAnalysisStatus.FAILED
                        elif output.analysis_status in {
                            ImageJobAnalysisStatus.PENDING,
                            ImageJobAnalysisStatus.ANALYZING,
                        }:
                            output.analysis_status = ImageJobAnalysisStatus.COMPLETED
            for output in job.outputs:
                if output.status != ImageJobOutputStatus.READY:
                    output.status = ImageJobOutputStatus.FAILED
                    output.progress = 100
                    output.error = output.error or "Image output did not complete"
            job.completed_at = now
            job.updated_at = now
            job.lease_owner = None
            job.lease_expires_at = None
            return job

        return await self.store.mutate(job_id, complete)

    async def _mark_failed(self, job_id: str, worker_id: str, exc: Exception) -> None:
        now = utcnow()
        if isinstance(exc, HTTPException):
            detail = exc.detail
            error = detail if isinstance(detail, str) else json.dumps(detail)
        else:
            error = str(exc)
        error = (error or exc.__class__.__name__)[:4000]

        def fail(job: ImageJobRecord) -> ImageJobRecord | None:
            if job.lease_owner != worker_id:
                return None
            job.status = ImageJobStatus.FAILED
            job.stage = ImageJobStatus.FAILED.value
            job.failed_images = max(
                job.failed_images, job.requested_images - job.completed_images
            )
            job.error = error
            for output in job.outputs:
                if output.status != ImageJobOutputStatus.READY:
                    output.status = ImageJobOutputStatus.FAILED
                    output.progress = 100
                    output.error = output.error or error
            job.completed_at = now
            job.updated_at = now
            job.lease_owner = None
            job.lease_expires_at = None
            return job

        await self.store.mutate(job_id, fail)

    async def _mark_cancelled(self, job_id: str, worker_id: str | None = None) -> None:
        now = utcnow()

        def cancel(job: ImageJobRecord) -> ImageJobRecord | None:
            if worker_id is not None and job.lease_owner != worker_id:
                return None
            if job.status in TERMINAL_IMAGE_JOB_STATUSES:
                return job
            job.status = ImageJobStatus.CANCELLED
            job.stage = ImageJobStatus.CANCELLED.value
            job.cancel_requested = True
            job.completed_at = now
            job.updated_at = now
            job.lease_owner = None
            job.lease_expires_at = None
            for output in job.outputs:
                if output.status != ImageJobOutputStatus.READY:
                    output.status = ImageJobOutputStatus.CANCELLED
                    output.progress = 100
            return job

        await self.store.mutate(job_id, cancel)

    async def _return_to_queue(self, job_id: str, worker_id: str) -> None:
        now = utcnow()

        def release(job: ImageJobRecord) -> ImageJobRecord | None:
            if job.lease_owner != worker_id:
                return None
            job.status = ImageJobStatus.QUEUED
            job.stage = ImageJobStatus.QUEUED.value
            job.progress = 0 if job.completed_images == 0 else job.progress
            job.updated_at = now
            job.lease_owner = None
            job.lease_expires_at = None
            for output in job.outputs:
                if output.status not in {
                    ImageJobOutputStatus.READY,
                    ImageJobOutputStatus.CANCELLED,
                }:
                    output.status = ImageJobOutputStatus.QUEUED
                    output.progress = 0
                    output.error = None
            return job

        await self.store.mutate(job_id, release)
