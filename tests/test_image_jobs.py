"""Unit and API-contract tests for durable image-generation jobs."""

import asyncio

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from backend.api.endpoints.image_jobs import router as image_jobs_router
from backend.jobs.manager import (
    ImageJobConflictError,
    ImageJobManager,
    ImageJobProgress,
)
from backend.jobs.queue import MemoryImageJobQueue
from backend.jobs.store import MemoryImageJobStore
from backend.jobs.store import CosmosImageJobStore
from backend.models.image_jobs import (
    ImageJobCreateRequest,
    ImageJobOutputStatus,
    ImageJobStatus,
)
from backend.models.images import (
    GPT_IMAGE_2_MODEL,
    ImagePipelineRequest,
    ImageSaveResponse,
    PipelineAnalysisOptions,
    PipelineSaveOptions,
)


def job_request(
    *, prompt: str = "A mountain observatory", count: int = 2, analyze: bool = True
) -> ImageJobCreateRequest:
    return ImageJobCreateRequest(
        request=ImagePipelineRequest(
            prompt=prompt,
            n=count,
            save_options=PipelineSaveOptions(enabled=True, save_all=True),
            analysis_options=PipelineAnalysisOptions(enabled=analyze),
        )
    )


def saved_result(count: int) -> ImageSaveResponse:
    return ImageSaveResponse(
        saved_images=[
            {
                "id": f"image-{index}",
                "url": f"https://example.test/{index}.png",
                "blob_name": f"image-{index}.png",
                "original_index": index + 1,
            }
            for index in range(count)
        ],
        total_saved=count,
        analyzed=True,
    )


@pytest.mark.asyncio
async def test_queued_job_persists_gpt_image_2_default():
    manager = manager_for(ConcurrentRunner(expected_concurrency=1), concurrency=1)
    await manager.start(run_workers=False)
    try:
        submitted = await manager.submit(job_request(count=1), owner_id="owner-a")
        persisted = await manager.get(submitted.id, owner_id="owner-a")
        record = await manager.store.get(submitted.id, owner_id="owner-a")

        assert submitted.model == GPT_IMAGE_2_MODEL
        assert persisted.model == GPT_IMAGE_2_MODEL
        assert record is not None
        assert record.pipeline_request["model"] == GPT_IMAGE_2_MODEL
    finally:
        await manager.close()


async def wait_for_status(
    manager: ImageJobManager,
    job_id: str,
    expected: ImageJobStatus,
    *,
    owner_id: str = "owner-a",
):
    async with asyncio.timeout(3):
        while True:
            job = await manager.get(job_id, owner_id=owner_id)
            if job.status == expected:
                return job
            await asyncio.sleep(0.01)


class ConcurrentRunner:
    def __init__(self, expected_concurrency: int = 2) -> None:
        self.expected_concurrency = expected_concurrency
        self.active = 0
        self.max_active = 0
        self.calls = 0
        self.all_started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, request, report_progress):
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.active >= self.expected_concurrency:
            self.all_started.set()
        try:
            await report_progress(
                ImageJobProgress(
                    status=ImageJobStatus.SAVING,
                    progress=65,
                    completed_images=0,
                    failed_images=0,
                )
            )
            await self.release.wait()
            await report_progress(
                ImageJobProgress(
                    status=ImageJobStatus.ANALYZING,
                    progress=90,
                    completed_images=request.n,
                    failed_images=0,
                )
            )
            return saved_result(request.n)
        finally:
            self.active -= 1


def manager_for(runner, *, concurrency: int = 2) -> ImageJobManager:
    return ImageJobManager(
        store=MemoryImageJobStore(),
        queue=MemoryImageJobQueue(),
        runner=runner,
        concurrency=concurrency,
        poll_interval=0.01,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
    )


@pytest.mark.asyncio
async def test_async_cosmos_queries_do_not_forward_sync_only_options():
    class AsyncItems:
        def __init__(self, values):
            self._values = iter(values)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._values)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class Container:
        def query_items(self, **kwargs):
            assert "enable_cross_partition_query" not in kwargs
            if "COUNT" in kwargs["query"]:
                return AsyncItems([0])
            return AsyncItems([])

    store = CosmosImageJobStore(
        endpoint="https://example.documents.azure.com",
        database_id="db",
        container_id="container",
    )
    store._container = Container()

    jobs, total = await store.list_jobs(owner_id="owner-a", limit=10)
    pending = await store.list_pending_dispatch()

    assert jobs == []
    assert total == 0
    assert pending == []


@pytest.mark.asyncio
async def test_workers_run_multiple_image_jobs_concurrently():
    runner = ConcurrentRunner()
    manager = manager_for(runner)
    await manager.start()
    try:
        first = await manager.submit(job_request(prompt="first"), owner_id="owner-a")
        second = await manager.submit(job_request(prompt="second"), owner_id="owner-a")

        await asyncio.wait_for(runner.all_started.wait(), timeout=1)
        assert runner.max_active == 2
        runner.release.set()

        first_done, second_done = await asyncio.gather(
            wait_for_status(manager, first.id, ImageJobStatus.COMPLETED),
            wait_for_status(manager, second.id, ImageJobStatus.COMPLETED),
        )
        assert first_done.completed_images == 2
        assert second_done.completed_images == 2
        assert first_done.progress == second_done.progress == 100
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_idempotency_key_runs_pipeline_once():
    calls = 0

    async def runner(request, report_progress):
        nonlocal calls
        calls += 1
        return saved_result(request.n)

    manager = manager_for(runner, concurrency=1)
    payload = job_request(count=1)
    payload.idempotency_key = "compose-submit-123"
    await manager.start()
    try:
        first = await manager.submit(payload, owner_id="owner-a")
        second = await manager.submit(payload, owner_id="owner-a")
        assert first.id == second.id
        await wait_for_status(manager, first.id, ImageJobStatus.COMPLETED)
        await asyncio.sleep(0.05)
        assert calls == 1
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_cancel_interrupts_an_in_flight_native_async_runner():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def runner(request, report_progress):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    manager = manager_for(runner, concurrency=1)
    await manager.start()
    try:
        submitted = await manager.submit(job_request(count=1), owner_id="owner-a")
        await asyncio.wait_for(started.wait(), timeout=1)
        accepted = await manager.cancel(submitted.id, owner_id="owner-a")
        assert accepted.status == ImageJobStatus.CANCEL_REQUESTED

        terminal = await wait_for_status(
            manager, submitted.id, ImageJobStatus.CANCELLED
        )
        assert terminal.cancel_requested is True
        assert cancelled.is_set()
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_failed_job_can_be_retried_as_a_new_job():
    calls = 0

    async def runner(request, report_progress):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("provider unavailable")
        return saved_result(request.n)

    manager = manager_for(runner, concurrency=1)
    await manager.start()
    try:
        failed = await manager.submit(job_request(count=1), owner_id="owner-a")
        failed = await wait_for_status(manager, failed.id, ImageJobStatus.FAILED)
        assert failed.error == "provider unavailable"

        retried = await manager.retry(failed.id, owner_id="owner-a")
        assert retried.id != failed.id
        assert retried.parent_job_id == failed.id
        completed = await wait_for_status(manager, retried.id, ImageJobStatus.COMPLETED)
        assert completed.completed_images == 1
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_jobs_are_scoped_to_the_request_owner():
    async def runner(request, report_progress):
        return saved_result(request.n)

    manager = manager_for(runner, concurrency=1)
    await manager.start()
    try:
        await manager.submit(job_request(count=1), owner_id="owner-a")
        jobs, total = await manager.list_jobs(owner_id="owner-b", limit=50)
        assert jobs == []
        assert total == 0
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_http_job_contract_returns_202_and_location_without_waiting():
    runner = ConcurrentRunner(expected_concurrency=1)
    manager = manager_for(runner, concurrency=1)
    app = FastAPI()
    app.state.image_job_manager = manager
    app.include_router(image_jobs_router, prefix="/api/v1/images")
    await manager.start()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://api.example.test"
        ) as client:
            response = await client.post(
                "/api/v1/images/jobs",
                headers={"X-Image-Job-Owner": "browser-123"},
                json=job_request(count=3).model_dump(mode="json"),
            )
            assert response.status_code == 202
            body = response.json()
            assert body["requested_images"] == 3
            assert response.headers["location"].endswith(
                f"/api/v1/images/jobs/{body['id']}"
            )
            assert not runner.release.is_set()

            get_response = await client.get(
                response.headers["location"],
                headers={"X-Image-Job-Owner": "browser-123"},
            )
            assert get_response.status_code == 200

            hidden_response = await client.get(
                response.headers["location"],
                headers={"X-Image-Job-Owner": "another-browser"},
            )
            assert hidden_response.status_code == 404
            unauthenticated = await client.get(response.headers["location"])
            assert unauthenticated.status_code == 401
            runner.release.set()
    finally:
        runner.release.set()
        await manager.close()


def test_async_job_rejects_ephemeral_unsaved_results():
    with pytest.raises(ValueError, match="save_options"):
        ImageJobCreateRequest(
            request=ImagePipelineRequest(
                prompt="not durable",
                save_options=PipelineSaveOptions(enabled=False),
            )
        )


@pytest.mark.asyncio
async def test_queued_cancel_is_immediately_terminal_without_a_worker():
    manager = manager_for(ConcurrentRunner(expected_concurrency=1), concurrency=1)
    await manager.start(run_workers=False)
    try:
        submitted = await manager.submit(job_request(count=2), owner_id="owner-a")
        cancelled = await manager.cancel(submitted.id, owner_id="owner-a")
        assert cancelled.status == ImageJobStatus.CANCELLED
        assert all(
            output.status == ImageJobOutputStatus.CANCELLED
            for output in cancelled.outputs
        )
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_idempotency_key_conflicts_when_request_content_changes():
    async def runner(request, report_progress):
        return saved_result(request.n)

    manager = manager_for(runner, concurrency=1)
    await manager.start(run_workers=False)
    try:
        first = job_request(prompt="first", count=1)
        first.idempotency_key = "same-key"
        await manager.submit(first, owner_id="owner-a")

        second = job_request(prompt="different", count=1)
        second.idempotency_key = "same-key"
        with pytest.raises(ImageJobConflictError, match="different image request"):
            await manager.submit(second, owner_id="owner-a")
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_retry_is_idempotent_for_concurrent_clicks():
    async def runner(request, report_progress):
        raise RuntimeError("permanent failure")

    manager = manager_for(runner, concurrency=1)
    await manager.start()
    try:
        failed = await manager.submit(job_request(count=1), owner_id="owner-a")
        failed = await wait_for_status(manager, failed.id, ImageJobStatus.FAILED)
        first, second = await asyncio.gather(
            manager.retry(failed.id, owner_id="owner-a"),
            manager.retry(failed.id, owner_id="owner-a"),
        )
        assert first.id == second.id
        assert first.parent_job_id == failed.id
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_progress_persists_ready_output_before_batch_completion():
    output_ready = asyncio.Event()
    release = asyncio.Event()

    async def runner(request, report_progress):
        await report_progress(
            ImageJobProgress(
                status=ImageJobStatus.SAVING,
                progress=70,
                completed_images=1,
                output_index=2,
                output_status=ImageJobOutputStatus.READY,
                asset={
                    "blob_name": "second.png",
                    "url": "https://example.test/second.png",
                    "original_index": 2,
                },
            )
        )
        output_ready.set()
        await release.wait()
        return saved_result(request.n)

    manager = manager_for(runner, concurrency=1)
    await manager.start()
    try:
        submitted = await manager.submit(job_request(count=2), owner_id="owner-a")
        await asyncio.wait_for(output_ready.wait(), timeout=1)
        active = await manager.get(submitted.id, owner_id="owner-a")
        assert active.status == ImageJobStatus.SAVING
        assert active.outputs[1].status == ImageJobOutputStatus.READY
        assert active.outputs[1].asset["blob_name"] == "second.png"
        release.set()
        await wait_for_status(manager, submitted.id, ImageJobStatus.COMPLETED)
    finally:
        release.set()
        await manager.close()


@pytest.mark.asyncio
async def test_dispatch_reconciliation_repairs_create_enqueue_gap():
    class FailFirstEnqueueQueue(MemoryImageJobQueue):
        def __init__(self):
            super().__init__()
            self.failures_remaining = 1

        async def enqueue(self, job_id: str, delay_seconds: int = 0) -> None:
            if self.failures_remaining:
                self.failures_remaining -= 1
                raise RuntimeError("queue unavailable")
            await super().enqueue(job_id, delay_seconds)

    queue = FailFirstEnqueueQueue()

    async def runner(request, report_progress):
        return saved_result(request.n)

    manager = ImageJobManager(
        store=MemoryImageJobStore(),
        queue=queue,
        runner=runner,
        concurrency=1,
        poll_interval=0.01,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
        reconcile_interval=0.01,
    )
    await manager.start(run_workers=False)
    try:
        with pytest.raises(RuntimeError, match="queue unavailable"):
            await manager.submit(job_request(count=1), owner_id="owner-a")

        async with asyncio.timeout(1):
            while True:
                message = await queue.receive()
                if message is not None:
                    break
                await asyncio.sleep(0.01)
        assert message.job_id
        await queue.delete(message)
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_coordination_failure_cancels_pipeline_before_requeue():
    class RenewFailureQueue(MemoryImageJobQueue):
        async def renew(self, message):
            raise RuntimeError("renew failed")

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def runner(request, report_progress):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    manager = ImageJobManager(
        store=MemoryImageJobStore(),
        queue=RenewFailureQueue(),
        runner=runner,
        concurrency=1,
        poll_interval=0.01,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
        heartbeat_interval=0.01,
        reconcile_interval=1,
    )
    await manager.start()
    try:
        await manager.submit(job_request(count=1), owner_id="owner-a")
        await asyncio.wait_for(started.wait(), timeout=1)
        await asyncio.wait_for(cancelled.wait(), timeout=1)
        async with asyncio.timeout(1):
            while manager._running_jobs:
                await asyncio.sleep(0.01)
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_cancel_racing_pipeline_completion_reaches_cancelled():
    runner_done = asyncio.Event()

    class CancelOnCompletionReadStore(MemoryImageJobStore):
        def __init__(self):
            super().__init__()
            self.injected = False

        async def get(self, job_id: str, owner_id: str | None = None):
            if runner_done.is_set() and not self.injected:
                self.injected = True

                def request_cancel(job):
                    job.cancel_requested = True
                    job.status = ImageJobStatus.CANCEL_REQUESTED
                    job.stage = ImageJobStatus.CANCEL_REQUESTED.value
                    return job

                await super().mutate(job_id, request_cancel)
            return await super().get(job_id, owner_id)

    async def runner(request, report_progress):
        runner_done.set()
        return saved_result(request.n)

    manager = ImageJobManager(
        store=CancelOnCompletionReadStore(),
        queue=MemoryImageJobQueue(),
        runner=runner,
        concurrency=1,
        poll_interval=0.01,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
    )
    await manager.start()
    try:
        submitted = await manager.submit(job_request(count=1), owner_id="owner-a")
        terminal = await wait_for_status(
            manager, submitted.id, ImageJobStatus.CANCELLED
        )
        assert terminal.cancel_requested is True
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_permanent_worker_failure_is_dead_lettered():
    queue = MemoryImageJobQueue()

    async def runner(request, report_progress):
        raise ValueError("invalid generation request")

    manager = ImageJobManager(
        store=MemoryImageJobStore(),
        queue=queue,
        runner=runner,
        concurrency=1,
        poll_interval=0.01,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
    )
    await manager.start()
    try:
        submitted = await manager.submit(job_request(count=1), owner_id="owner-a")
        failed = await wait_for_status(manager, submitted.id, ImageJobStatus.FAILED)
        assert all(
            output.status == ImageJobOutputStatus.FAILED for output in failed.outputs
        )
        assert queue.dead_letters == [
            {
                "job_id": submitted.id,
                "reason": "invalid generation request",
                "dequeue_count": 1,
            }
        ]
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_transient_provider_failure_retries_without_dead_lettering():
    queue = MemoryImageJobQueue()
    calls = 0

    async def runner(request, report_progress):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPException(status_code=503, detail="provider busy")
        return saved_result(request.n)

    manager = ImageJobManager(
        store=MemoryImageJobStore(),
        queue=queue,
        runner=runner,
        concurrency=1,
        poll_interval=0.01,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
        max_attempts=3,
    )
    await manager.start()
    try:
        submitted = await manager.submit(job_request(count=1), owner_id="owner-a")
        completed = await wait_for_status(
            manager,
            submitted.id,
            ImageJobStatus.COMPLETED,
        )
        assert calls == 2
        assert completed.attempt == 2
        assert queue.dead_letters == []
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_duplicate_queue_delivery_does_not_run_pipeline_twice():
    queue = MemoryImageJobQueue()
    release = asyncio.Event()
    calls = 0

    async def runner(request, report_progress):
        nonlocal calls
        calls += 1
        await release.wait()
        return saved_result(request.n)

    manager = ImageJobManager(
        store=MemoryImageJobStore(),
        queue=queue,
        runner=runner,
        concurrency=2,
        poll_interval=0.01,
        visibility_timeout=1,
        cancellation_poll_interval=0.01,
    )
    await manager.start()
    try:
        submitted = await manager.submit(job_request(count=1), owner_id="owner-a")
        await queue.enqueue(submitted.id)
        async with asyncio.timeout(1):
            while calls == 0:
                await asyncio.sleep(0.01)
        release.set()
        await wait_for_status(manager, submitted.id, ImageJobStatus.COMPLETED)
        await asyncio.sleep(0.05)
        assert calls == 1
    finally:
        release.set()
        await manager.close()
