"""Atomic job-state stores for local development and Azure Cosmos DB."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol

from azure.core import MatchConditions
from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

from backend.models.image_jobs import ImageJobRecord, ImageJobStatus


JobMutator = Callable[[ImageJobRecord], ImageJobRecord | None]


def image_job_partition(job_id: str) -> str:
    """Spread job documents across the existing /media_type partition key."""

    return f"image_job_{job_id.replace('-', '')[:2].lower()}"


class ImageJobStore(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def health_check(self) -> None: ...

    async def create(self, job: ImageJobRecord) -> tuple[ImageJobRecord, bool]: ...

    async def get(
        self, job_id: str, owner_id: str | None = None
    ) -> ImageJobRecord | None: ...

    async def list_jobs(
        self,
        owner_id: str,
        limit: int,
        statuses: set[ImageJobStatus] | None = None,
    ) -> tuple[list[ImageJobRecord], int]: ...

    async def list_pending_dispatch(self, limit: int = 100) -> list[ImageJobRecord]: ...

    async def mutate(
        self,
        job_id: str,
        mutator: JobMutator,
        owner_id: str | None = None,
    ) -> ImageJobRecord | None: ...


class MemoryImageJobStore:
    """Process-local implementation used by tests and dependency-free local runs."""

    def __init__(self) -> None:
        self._jobs: dict[str, ImageJobRecord] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health_check(self) -> None:
        return None

    @staticmethod
    def _copy(job: ImageJobRecord) -> ImageJobRecord:
        return ImageJobRecord.model_validate(job.model_dump(mode="python"))

    async def create(self, job: ImageJobRecord) -> tuple[ImageJobRecord, bool]:
        async with self._lock:
            existing = self._jobs.get(job.id)
            if existing is not None:
                return self._copy(existing), False
            self._jobs[job.id] = self._copy(job)
            return self._copy(job), True

    async def get(
        self, job_id: str, owner_id: str | None = None
    ) -> ImageJobRecord | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None or (owner_id is not None and job.owner_id != owner_id):
                return None
            return self._copy(job)

    async def list_jobs(
        self,
        owner_id: str,
        limit: int,
        statuses: set[ImageJobStatus] | None = None,
    ) -> tuple[list[ImageJobRecord], int]:
        async with self._lock:
            jobs = [job for job in self._jobs.values() if job.owner_id == owner_id]
            if statuses:
                jobs = [job for job in jobs if job.status in statuses]
            jobs.sort(key=lambda job: job.created_at, reverse=True)
            return [self._copy(job) for job in jobs[:limit]], len(jobs)

    async def list_pending_dispatch(self, limit: int = 100) -> list[ImageJobRecord]:
        async with self._lock:
            jobs = [
                job
                for job in self._jobs.values()
                if job.status == ImageJobStatus.QUEUED
                and job.dispatched_at is None
                and not job.cancel_requested
            ]
            jobs.sort(key=lambda job: job.created_at)
            return [self._copy(job) for job in jobs[: max(1, min(limit, 100))]]

    async def mutate(
        self,
        job_id: str,
        mutator: JobMutator,
        owner_id: str | None = None,
    ) -> ImageJobRecord | None:
        async with self._lock:
            current = self._jobs.get(job_id)
            if current is None or (
                owner_id is not None and current.owner_id != owner_id
            ):
                return None
            updated = mutator(self._copy(current))
            if updated is None:
                return None
            updated.revision = current.revision + 1
            self._jobs[job_id] = self._copy(updated)
            return self._copy(updated)


class CosmosImageJobStore:
    """Cosmos implementation using optimistic ETags for multi-replica workers."""

    def __init__(
        self,
        *,
        endpoint: str,
        database_id: str,
        container_id: str,
    ) -> None:
        self._endpoint = endpoint
        self._database_id = database_id
        self._container_id = container_id
        self._credential: DefaultAzureCredential | None = None
        self._client: CosmosClient | None = None
        self._container = None

    async def start(self) -> None:
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(self._endpoint, credential=self._credential)
        database = self._client.get_database_client(self._database_id)
        self._container = database.get_container_client(self._container_id)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._credential is not None:
            await self._credential.close()
        self._container = None
        self._client = None
        self._credential = None

    async def health_check(self) -> None:
        await self._require_container().read()

    def _require_container(self):
        if self._container is None:
            raise RuntimeError("Cosmos image job store has not been started")
        return self._container

    @staticmethod
    def _record(raw: dict) -> ImageJobRecord:
        return ImageJobRecord.model_validate(raw)

    @staticmethod
    def _document(job: ImageJobRecord) -> dict:
        document = job.model_dump(mode="json")
        for key in tuple(document):
            if key.startswith("_"):
                document.pop(key, None)
        return document

    async def create(self, job: ImageJobRecord) -> tuple[ImageJobRecord, bool]:
        container = self._require_container()
        try:
            raw = await container.create_item(body=self._document(job))
            return self._record(raw), True
        except cosmos_exceptions.CosmosResourceExistsError:
            existing = await self.get(job.id, owner_id=job.owner_id)
            if existing is None:
                raise
            return existing, False

    async def get(
        self, job_id: str, owner_id: str | None = None
    ) -> ImageJobRecord | None:
        container = self._require_container()
        try:
            raw = await container.read_item(
                item=job_id,
                partition_key=image_job_partition(job_id),
            )
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None
        record = self._record(raw)
        if owner_id is not None and record.owner_id != owner_id:
            return None
        return record

    async def list_jobs(
        self,
        owner_id: str,
        limit: int,
        statuses: set[ImageJobStatus] | None = None,
    ) -> tuple[list[ImageJobRecord], int]:
        container = self._require_container()
        parameters: list[dict[str, object]] = [{"name": "@owner_id", "value": owner_id}]
        status_clause = ""
        if statuses:
            names: list[str] = []
            for index, status in enumerate(
                sorted(statuses, key=lambda value: value.value)
            ):
                name = f"@status_{index}"
                names.append(name)
                parameters.append({"name": name, "value": status.value})
            status_clause = f" AND c.status IN ({', '.join(names)})"

        where = (
            "c.doc_type = 'image_generation_job' "
            "AND c.owner_id = @owner_id"
            f"{status_clause}"
        )
        safe_limit = max(1, min(limit, 100))
        query = (
            f"SELECT * FROM c WHERE {where} "
            f"ORDER BY c.created_at DESC OFFSET 0 LIMIT {safe_limit}"
        )
        records = [
            self._record(raw)
            async for raw in container.query_items(
                query=query,
                parameters=parameters,
            )
        ]
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        counts = [
            value
            async for value in container.query_items(
                query=count_query,
                parameters=parameters,
            )
        ]
        return records, int(counts[0]) if counts else 0

    async def list_pending_dispatch(self, limit: int = 100) -> list[ImageJobRecord]:
        container = self._require_container()
        safe_limit = max(1, min(limit, 100))
        query = (
            "SELECT * FROM c WHERE c.doc_type = 'image_generation_job' "
            "AND c.status = 'queued' "
            "AND (NOT IS_DEFINED(c.dispatched_at) OR IS_NULL(c.dispatched_at)) "
            "AND (NOT IS_DEFINED(c.cancel_requested) OR c.cancel_requested = false) "
            f"ORDER BY c.created_at ASC OFFSET 0 LIMIT {safe_limit}"
        )
        return [
            self._record(raw)
            async for raw in container.query_items(
                query=query,
            )
        ]

    async def mutate(
        self,
        job_id: str,
        mutator: JobMutator,
        owner_id: str | None = None,
    ) -> ImageJobRecord | None:
        container = self._require_container()
        for _ in range(5):
            try:
                raw = await container.read_item(
                    item=job_id,
                    partition_key=image_job_partition(job_id),
                )
            except cosmos_exceptions.CosmosResourceNotFoundError:
                return None

            current = self._record(raw)
            if owner_id is not None and current.owner_id != owner_id:
                return None
            updated = mutator(current)
            if updated is None:
                return None
            updated.revision = current.revision + 1
            try:
                replaced = await container.replace_item(
                    item=raw,
                    body=self._document(updated),
                    etag=raw.get("_etag"),
                    match_condition=MatchConditions.IfNotModified,
                )
                return self._record(replaced)
            except cosmos_exceptions.CosmosHttpResponseError as exc:
                if exc.status_code != 412:
                    raise
        raise RuntimeError(f"Concurrent updates did not settle for image job {job_id}")
