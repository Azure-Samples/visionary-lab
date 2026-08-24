"""Native async Cosmos repository for generated asset metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AsyncCosmosAssetService:
    """Reusable aio client for worker-side asset metadata writes."""

    def __init__(self, *, endpoint: str, database_id: str, container_id: str) -> None:
        self._endpoint = endpoint
        self._database_id = database_id
        self._container_id = container_id
        self._credential: DefaultAzureCredential | None = None
        self._client: CosmosClient | None = None
        self._container = None

    async def start(self) -> None:
        if self._container is not None:
            return
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

    def _require_container(self):
        if self._container is None:
            raise RuntimeError("Async Cosmos asset service has not been started")
        return self._container

    async def upsert_asset_metadata(self, asset_data: dict[str, Any]) -> dict[str, Any]:
        container = self._require_container()
        payload = dict(asset_data)
        asset_id = str(payload["id"])
        media_type = str(payload.get("media_type") or "unknown")
        now = utcnow_iso()
        try:
            existing = await container.read_item(
                item=asset_id,
                partition_key=media_type,
            )
        except cosmos_exceptions.CosmosResourceNotFoundError:
            existing = None
        payload["created_at"] = (
            existing.get("created_at") if existing is not None else now
        )
        payload["updated_at"] = now
        payload["media_type"] = media_type
        payload["doc_type"] = "asset_metadata"
        return await container.upsert_item(body=payload)

    async def update_asset_metadata(
        self,
        asset_id: str,
        media_type: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        container = self._require_container()
        existing = await container.read_item(
            item=asset_id,
            partition_key=media_type,
        )
        existing.update(updates)
        existing["updated_at"] = utcnow_iso()
        return await container.replace_item(item=asset_id, body=existing)
