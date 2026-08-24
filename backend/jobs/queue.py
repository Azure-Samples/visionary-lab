"""Queue adapters for durable image-generation work dispatch."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from azure.identity.aio import DefaultAzureCredential
from azure.storage.queue.aio import QueueClient


@dataclass
class ImageJobQueueMessage:
    id: str
    pop_receipt: str
    job_id: str
    dequeue_count: int = 1


class ImageJobQueue(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def health_check(self) -> None: ...

    async def enqueue(self, job_id: str, delay_seconds: int = 0) -> None: ...

    async def receive(self) -> ImageJobQueueMessage | None: ...

    async def delete(self, message: ImageJobQueueMessage) -> None: ...

    async def renew(self, message: ImageJobQueueMessage) -> None: ...

    async def release(
        self, message: ImageJobQueueMessage, delay_seconds: int = 0
    ) -> None: ...

    async def dead_letter(self, message: ImageJobQueueMessage, reason: str) -> None: ...


class MemoryImageJobQueue:
    """Small asyncio queue used for tests and local, single-process development."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self._delayed_tasks: set[asyncio.Task[None]] = set()
        self.dead_letters: list[dict[str, object]] = []

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        for task in self._delayed_tasks:
            task.cancel()
        if self._delayed_tasks:
            await asyncio.gather(*self._delayed_tasks, return_exceptions=True)
        self._delayed_tasks.clear()

    async def health_check(self) -> None:
        return None

    async def _enqueue_after(self, job_id: str, delay_seconds: int, count: int) -> None:
        await asyncio.sleep(delay_seconds)
        await self._queue.put((job_id, count))

    async def enqueue(self, job_id: str, delay_seconds: int = 0) -> None:
        if delay_seconds <= 0:
            await self._queue.put((job_id, 0))
            return
        task = asyncio.create_task(self._enqueue_after(job_id, delay_seconds, 0))
        self._delayed_tasks.add(task)
        task.add_done_callback(self._delayed_tasks.discard)

    async def receive(self) -> ImageJobQueueMessage | None:
        try:
            job_id, previous_count = await asyncio.wait_for(
                self._queue.get(), timeout=0.25
            )
        except TimeoutError:
            return None
        return ImageJobQueueMessage(
            id=str(uuid.uuid4()),
            pop_receipt=str(uuid.uuid4()),
            job_id=job_id,
            dequeue_count=previous_count + 1,
        )

    async def delete(self, message: ImageJobQueueMessage) -> None:
        self._queue.task_done()

    async def renew(self, message: ImageJobQueueMessage) -> None:
        return None

    async def release(
        self, message: ImageJobQueueMessage, delay_seconds: int = 0
    ) -> None:
        self._queue.task_done()
        if delay_seconds <= 0:
            await self._queue.put((message.job_id, message.dequeue_count))
            return
        task = asyncio.create_task(
            self._enqueue_after(message.job_id, delay_seconds, message.dequeue_count)
        )
        self._delayed_tasks.add(task)
        task.add_done_callback(self._delayed_tasks.discard)

    async def dead_letter(self, message: ImageJobQueueMessage, reason: str) -> None:
        self.dead_letters.append(
            {
                "job_id": message.job_id,
                "reason": reason,
                "dequeue_count": message.dequeue_count,
            }
        )
        self._queue.task_done()


class AzureStorageImageJobQueue:
    """Managed-identity adapter for Azure Storage Queue."""

    def __init__(
        self,
        *,
        account_url: str,
        queue_name: str,
        poison_queue_name: str,
        visibility_timeout: int,
    ) -> None:
        self._account_url = account_url
        self._queue_name = queue_name
        self._poison_queue_name = poison_queue_name
        self._visibility_timeout = visibility_timeout
        self._credential: DefaultAzureCredential | None = None
        self._client: QueueClient | None = None
        self._poison_client: QueueClient | None = None

    async def start(self) -> None:
        self._credential = DefaultAzureCredential()
        self._client = QueueClient(
            account_url=self._account_url,
            queue_name=self._queue_name,
            credential=self._credential,
        )
        self._poison_client = QueueClient(
            account_url=self._account_url,
            queue_name=self._poison_queue_name,
            credential=self._credential,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._poison_client is not None:
            await self._poison_client.close()
        if self._credential is not None:
            await self._credential.close()
        self._client = None
        self._poison_client = None
        self._credential = None

    async def health_check(self) -> None:
        await asyncio.gather(
            self._require_client().get_queue_properties(),
            self._require_poison_client().get_queue_properties(),
        )

    def _require_client(self) -> QueueClient:
        if self._client is None:
            raise RuntimeError("Azure image job queue has not been started")
        return self._client

    def _require_poison_client(self) -> QueueClient:
        if self._poison_client is None:
            raise RuntimeError("Azure image job poison queue has not been started")
        return self._poison_client

    async def enqueue(self, job_id: str, delay_seconds: int = 0) -> None:
        client = self._require_client()
        content = json.dumps({"job_id": job_id}, separators=(",", ":"))
        kwargs = {"visibility_timeout": delay_seconds} if delay_seconds else {}
        await client.send_message(content, **kwargs)

    async def receive(self) -> ImageJobQueueMessage | None:
        client = self._require_client()
        messages = client.receive_messages(
            messages_per_page=1,
            visibility_timeout=self._visibility_timeout,
        )
        async for message in messages:
            try:
                payload = json.loads(message.content)
                job_id = str(payload["job_id"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                await client.delete_message(message.id, message.pop_receipt)
                return None
            return ImageJobQueueMessage(
                id=message.id,
                pop_receipt=message.pop_receipt,
                job_id=job_id,
                dequeue_count=message.dequeue_count or 1,
            )
        return None

    async def delete(self, message: ImageJobQueueMessage) -> None:
        await self._require_client().delete_message(message.id, message.pop_receipt)

    async def renew(self, message: ImageJobQueueMessage) -> None:
        receipt = await self._require_client().update_message(
            message.id,
            pop_receipt=message.pop_receipt,
            visibility_timeout=self._visibility_timeout,
        )
        message.pop_receipt = receipt.pop_receipt

    async def release(
        self, message: ImageJobQueueMessage, delay_seconds: int = 0
    ) -> None:
        receipt = await self._require_client().update_message(
            message.id,
            pop_receipt=message.pop_receipt,
            visibility_timeout=delay_seconds,
        )
        message.pop_receipt = receipt.pop_receipt

    async def dead_letter(self, message: ImageJobQueueMessage, reason: str) -> None:
        content = json.dumps(
            {
                "job_id": message.job_id,
                "reason": reason[:4000],
                "dequeue_count": message.dequeue_count,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
            separators=(",", ":"),
        )
        await self._require_poison_client().send_message(content)
        await self.delete(message)
