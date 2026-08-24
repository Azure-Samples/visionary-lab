"""Dependency construction for image jobs without import-time network access."""

from backend.jobs.manager import DefaultImagePipelineRunner, ImageJobManager
from backend.jobs.queue import AzureStorageImageJobQueue, MemoryImageJobQueue
from backend.jobs.store import CosmosImageJobStore, MemoryImageJobStore


def create_image_job_manager(settings) -> ImageJobManager:
    mode = settings.IMAGE_JOB_MODE.strip().lower()
    if mode not in {"auto", "azure", "memory"}:
        raise ValueError("IMAGE_JOB_MODE must be one of: auto, azure, memory")

    has_cosmos = bool(settings.AZURE_COSMOS_DB_ENDPOINT)
    has_queue = bool(settings.AZURE_STORAGE_QUEUE_URL)
    if mode == "auto" and has_cosmos != has_queue:
        raise ValueError(
            "Durable image jobs require both AZURE_COSMOS_DB_ENDPOINT and "
            "AZURE_STORAGE_QUEUE_URL, or neither for local memory mode"
        )
    use_azure = mode == "azure" or (mode == "auto" and has_cosmos and has_queue)

    if use_azure:
        if not has_cosmos or not has_queue:
            raise ValueError(
                "IMAGE_JOB_MODE=azure requires AZURE_COSMOS_DB_ENDPOINT and "
                "AZURE_STORAGE_QUEUE_URL"
            )
        store = CosmosImageJobStore(
            endpoint=settings.AZURE_COSMOS_DB_ENDPOINT,
            database_id=settings.AZURE_COSMOS_DB_ID,
            container_id=settings.AZURE_COSMOS_CONTAINER_ID,
        )
        queue = AzureStorageImageJobQueue(
            account_url=settings.AZURE_STORAGE_QUEUE_URL,
            queue_name=settings.AZURE_STORAGE_QUEUE_NAME,
            poison_queue_name=settings.AZURE_STORAGE_POISON_QUEUE_NAME,
            visibility_timeout=settings.IMAGE_JOB_VISIBILITY_TIMEOUT_SECONDS,
        )
    else:
        store = MemoryImageJobStore()
        queue = MemoryImageJobQueue()

    return ImageJobManager(
        store=store,
        queue=queue,
        runner=DefaultImagePipelineRunner(),
        concurrency=settings.IMAGE_JOB_CONCURRENCY,
        poll_interval=settings.IMAGE_JOB_POLL_INTERVAL_SECONDS,
        visibility_timeout=settings.IMAGE_JOB_VISIBILITY_TIMEOUT_SECONDS,
        cancellation_poll_interval=settings.IMAGE_JOB_CANCELLATION_POLL_SECONDS,
        heartbeat_interval=(settings.IMAGE_JOB_HEARTBEAT_INTERVAL_SECONDS or None),
        reconcile_interval=settings.IMAGE_JOB_RECONCILE_INTERVAL_SECONDS,
        max_attempts=settings.IMAGE_JOB_MAX_ATTEMPTS,
        retention_seconds=settings.IMAGE_JOB_RETENTION_SECONDS,
    )
