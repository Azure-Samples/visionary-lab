# Configure logging first, before other imports
from .core.logging_config import setup_logging

setup_logging()

from contextlib import asynccontextmanager  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
import os  # noqa: E402
import uvicorn  # noqa: E402
from .core.config import settings  # noqa: E402
from .core import close_core_clients, warm_core_clients  # noqa: E402
from .api.endpoints import (  # noqa: E402
    env,
    gallery,
    image_jobs,
    images,
    metadata_router,
    storylines,
)
from .jobs.factory import create_image_job_manager  # noqa: E402
from .storylines.factory import create_storyline_manager  # noqa: E402


# Create directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.IMAGE_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own async clients and worker tasks for the full application lifetime."""

    role = settings.IMAGE_JOB_ROLE.strip().lower()
    if role not in {"api", "worker", "all"}:
        raise ValueError("IMAGE_JOB_ROLE must be one of: api, worker, all")
    await warm_core_clients()
    image_job_manager = create_image_job_manager(settings)
    app.state.image_job_manager = image_job_manager
    await image_job_manager.start(run_workers=role in {"worker", "all"})
    storyline_manager = create_storyline_manager(settings, image_job_manager)
    app.state.storyline_manager = storyline_manager
    await storyline_manager.start()
    try:
        yield
    finally:
        await storyline_manager.close()
        await image_job_manager.close()
        await images.pipeline_service.close()
        await close_core_clients()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set up CORS for direct local development. Production browser traffic uses
# the authenticated same-origin frontend proxy.
cors_origins = [
    origin.strip()
    for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=bool(cors_origins and cors_origins != ["*"]),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(
    images.router, prefix=f"{settings.API_V1_STR}/images", tags=["images"]
)
app.include_router(
    image_jobs.router, prefix=f"{settings.API_V1_STR}/images", tags=["image jobs"]
)
app.include_router(
    storylines.router,
    prefix=f"{settings.API_V1_STR}/storylines",
    tags=["storylines"],
)
app.include_router(
    gallery.router, prefix=f"{settings.API_V1_STR}/gallery", tags=["gallery"]
)
app.include_router(
    metadata_router.router, prefix=f"{settings.API_V1_STR}/metadata", tags=["metadata"]
)
app.include_router(env.router, prefix=f"{settings.API_V1_STR}", tags=["env"])


@app.get("/")
def read_root():
    return {"message": "Welcome to AI Content Lab API"}


@app.get(f"{settings.API_V1_STR}/health")
async def health_check(request: Request):
    manager = getattr(request.app.state, "image_job_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Image job service unavailable")
    storyline_manager = getattr(request.app.state, "storyline_manager", None)
    if storyline_manager is None:
        raise HTTPException(status_code=503, detail="Storyline service unavailable")
    try:
        dependencies = await manager.health_check()
        await storyline_manager.health_check()
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Image job dependencies unavailable"
        ) from exc
    return {
        "status": "ok",
        "image_jobs": dependencies,
        "storylines": "ok",
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
