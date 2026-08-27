"""Atomic stores for storyline aggregates."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol

from azure.core import MatchConditions
from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

from backend.models.storylines import (
    ACTIVE_STORYLINE_STATUSES,
    StorylineRecord,
    StorylineStatus,
)


class StorylineStoreConflictError(RuntimeError):
    """Raised when a revision or ETag precondition no longer matches."""


StorylineMutator = Callable[[StorylineRecord], StorylineRecord | None]


class StorylineStore(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def health_check(self) -> None: ...

    async def create(
        self, storyline: StorylineRecord
    ) -> tuple[StorylineRecord, bool]: ...

    async def get(
        self, storyline_id: str, owner_id: str | None = None
    ) -> StorylineRecord | None: ...

    async def list_storylines(
        self,
        owner_id: str,
        *,
        limit: int,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> tuple[list[StorylineRecord], int]: ...

    async def list_active(
        self,
        limit: int = 100,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> list[StorylineRecord]: ...

    async def mutate(
        self,
        storyline_id: str,
        mutator: StorylineMutator,
        *,
        owner_id: str | None = None,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> StorylineRecord | None: ...


class MemoryStorylineStore:
    """Process-local store used by tests and dependency-free local runs."""

    def __init__(self) -> None:
        self._storylines: dict[str, StorylineRecord] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def health_check(self) -> None:
        return None

    @staticmethod
    def _copy(storyline: StorylineRecord) -> StorylineRecord:
        return StorylineRecord.model_validate(storyline.model_dump(mode="python"))

    @staticmethod
    def _etag(revision: int) -> str:
        return f"memory-{revision}"

    async def create(self, storyline: StorylineRecord) -> tuple[StorylineRecord, bool]:
        async with self._lock:
            existing = self._storylines.get(storyline.id)
            if existing is not None:
                return self._copy(existing), False
            persisted = storyline.model_copy(
                update={"etag": storyline.etag or self._etag(storyline.revision)}
            )
            self._storylines[storyline.id] = self._copy(persisted)
            return self._copy(persisted), True

    async def get(
        self, storyline_id: str, owner_id: str | None = None
    ) -> StorylineRecord | None:
        async with self._lock:
            storyline = self._storylines.get(storyline_id)
            if storyline is None or (
                owner_id is not None and storyline.owner_id != owner_id
            ):
                return None
            return self._copy(storyline)

    async def list_storylines(
        self,
        owner_id: str,
        *,
        limit: int,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> tuple[list[StorylineRecord], int]:
        async with self._lock:
            storylines = [
                storyline
                for storyline in self._storylines.values()
                if storyline.owner_id == owner_id
            ]
            if statuses:
                storylines = [
                    storyline
                    for storyline in storylines
                    if storyline.status in statuses
                ]
            storylines.sort(key=lambda storyline: storyline.created_at, reverse=True)
            page = storylines[offset : offset + limit]
            return [self._copy(storyline) for storyline in page], len(storylines)

    async def list_active(
        self,
        limit: int = 100,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> list[StorylineRecord]:
        async with self._lock:
            selected_statuses = statuses or ACTIVE_STORYLINE_STATUSES
            storylines = [
                storyline
                for storyline in self._storylines.values()
                if storyline.status in selected_statuses
            ]
            storylines.sort(
                key=lambda storyline: (storyline.updated_at, storyline.created_at)
            )
            return [
                self._copy(storyline)
                for storyline in storylines[
                    max(0, offset) : max(0, offset) + max(1, min(limit, 100))
                ]
            ]

    async def mutate(
        self,
        storyline_id: str,
        mutator: StorylineMutator,
        *,
        owner_id: str | None = None,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> StorylineRecord | None:
        async with self._lock:
            current = self._storylines.get(storyline_id)
            if current is None or (
                owner_id is not None and current.owner_id != owner_id
            ):
                return None
            self._check_preconditions(current, expected_revision, expected_etag)
            updated = mutator(self._copy(current))
            if updated is None:
                return None
            next_revision = current.revision + 1
            updated = updated.model_copy(
                update={
                    "revision": next_revision,
                    "etag": self._etag(next_revision),
                }
            )
            self._storylines[storyline_id] = self._copy(updated)
            return self._copy(updated)

    @staticmethod
    def _check_preconditions(
        current: StorylineRecord,
        expected_revision: int | None,
        expected_etag: str | None,
    ) -> None:
        if expected_revision is not None and current.revision != expected_revision:
            raise StorylineStoreConflictError(
                f"Expected storyline revision {expected_revision}, found {current.revision}"
            )
        if expected_etag is not None and current.etag != expected_etag:
            raise StorylineStoreConflictError("The storyline ETag is stale")


class CosmosStorylineStore:
    """Cosmos implementation sharing the metadata container and /media_type key."""

    def __init__(self, *, endpoint: str, database_id: str, container_id: str) -> None:
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
            raise RuntimeError("Cosmos storyline store has not been started")
        return self._container

    @staticmethod
    def _record(raw: dict) -> StorylineRecord:
        payload = dict(raw)
        payload["etag"] = payload.get("_etag") or payload.get("etag")
        return StorylineRecord.model_validate(payload)

    @staticmethod
    def _document(storyline: StorylineRecord) -> dict:
        document = storyline.model_dump(
            mode="json",
            by_alias=True,
            exclude={"etag"},
        )
        # Cosmos rejects an explicit null per-item TTL. Omitting the property
        # inherits the container default, while a configured positive TTL is
        # still serialized below.
        if document.get("ttl") is None:
            document.pop("ttl", None)
        for key in tuple(document):
            if key.startswith("_"):
                document.pop(key, None)
        return document

    async def create(self, storyline: StorylineRecord) -> tuple[StorylineRecord, bool]:
        container = self._require_container()
        try:
            raw = await container.create_item(body=self._document(storyline))
            return self._record(raw), True
        except cosmos_exceptions.CosmosResourceExistsError:
            existing = await self.get(storyline.id, owner_id=storyline.owner_id)
            if existing is None:
                raise
            return existing, False

    async def get(
        self, storyline_id: str, owner_id: str | None = None
    ) -> StorylineRecord | None:
        container = self._require_container()
        try:
            raw = await container.read_item(
                item=storyline_id,
                partition_key="storyline",
            )
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None
        record = self._record(raw)
        if owner_id is not None and record.owner_id != owner_id:
            return None
        return record

    async def list_storylines(
        self,
        owner_id: str,
        *,
        limit: int,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> tuple[list[StorylineRecord], int]:
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
            "c.doc_type = 'storyline' AND c.media_type = 'storyline' "
            "AND c.owner_id = @owner_id"
            f"{status_clause}"
        )
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        query = (
            f"SELECT * FROM c WHERE {where} ORDER BY c.created_at DESC "
            f"OFFSET {safe_offset} LIMIT {safe_limit}"
        )
        records = [
            self._record(raw)
            async for raw in container.query_items(query=query, parameters=parameters)
        ]
        counts = [
            value
            async for value in container.query_items(
                query=f"SELECT VALUE COUNT(1) FROM c WHERE {where}",
                parameters=parameters,
            )
        ]
        return records, int(counts[0]) if counts else 0

    async def list_active(
        self,
        limit: int = 100,
        offset: int = 0,
        statuses: set[StorylineStatus] | None = None,
    ) -> list[StorylineRecord]:
        container = self._require_container()
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        selected_statuses = statuses or ACTIVE_STORYLINE_STATUSES
        status_values = sorted(status.value for status in selected_statuses)
        parameters = [
            {"name": f"@status_{index}", "value": value}
            for index, value in enumerate(status_values)
        ]
        names = ", ".join(parameter["name"] for parameter in parameters)
        query = (
            "SELECT * FROM c WHERE c.doc_type = 'storyline' "
            "AND c.media_type = 'storyline' "
            f"AND c.status IN ({names}) "
            f"ORDER BY c.updated_at ASC OFFSET {safe_offset} LIMIT {safe_limit}"
        )
        return [
            self._record(raw)
            async for raw in container.query_items(query=query, parameters=parameters)
        ]

    async def mutate(
        self,
        storyline_id: str,
        mutator: StorylineMutator,
        *,
        owner_id: str | None = None,
        expected_revision: int | None = None,
        expected_etag: str | None = None,
    ) -> StorylineRecord | None:
        container = self._require_container()
        for _ in range(5):
            try:
                raw = await container.read_item(
                    item=storyline_id,
                    partition_key="storyline",
                )
            except cosmos_exceptions.CosmosResourceNotFoundError:
                return None

            current = self._record(raw)
            if owner_id is not None and current.owner_id != owner_id:
                return None
            MemoryStorylineStore._check_preconditions(
                current, expected_revision, expected_etag
            )
            updated = mutator(current)
            if updated is None:
                return None
            updated = updated.model_copy(update={"revision": current.revision + 1})
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
                if expected_revision is not None or expected_etag is not None:
                    raise StorylineStoreConflictError(
                        "The storyline changed while the update was being applied"
                    ) from exc
        raise StorylineStoreConflictError(
            f"Concurrent updates did not settle for storyline {storyline_id}"
        )
