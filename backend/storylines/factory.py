"""Construct the storyline service without import-time network access."""

from backend.core.resources import get_core_clients
from backend.core.storyline_planner import StorylinePlanner, UnavailableStorylinePlanner
from backend.storylines.manager import StorylineManager
from backend.storylines.orchestrator import StorylineOrchestrator
from backend.storylines.store import CosmosStorylineStore, MemoryStorylineStore


def create_storyline_manager(settings, image_job_manager) -> StorylineOrchestrator:
    mode = settings.IMAGE_JOB_MODE.strip().lower()
    use_cosmos = mode != "memory" and bool(settings.AZURE_COSMOS_DB_ENDPOINT)
    if use_cosmos:
        store = CosmosStorylineStore(
            endpoint=settings.AZURE_COSMOS_DB_ENDPOINT,
            database_id=settings.AZURE_COSMOS_DB_ID,
            container_id=settings.AZURE_COSMOS_CONTAINER_ID,
        )
    else:
        store = MemoryStorylineStore()
    clients = get_core_clients()
    planner = (
        StorylinePlanner(
            clients.async_llm_client,
            settings.LLM_DEPLOYMENT,
        )
        if settings.LLM_DEPLOYMENT
        else UnavailableStorylinePlanner()
    )
    return StorylineOrchestrator(
        manager=StorylineManager(store=store),
        image_jobs=image_job_manager,
        planner=planner,  # type: ignore[arg-type]
        reconcile_interval=settings.IMAGE_JOB_RECONCILE_INTERVAL_SECONDS,
    )
