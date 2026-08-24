# Configure logging first, before other imports
from .core.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
import os  # noqa: E402
import uvicorn  # noqa: E402
from .core.config import settings  # noqa: E402
from .api.endpoints import images, metadata_router, gallery, env  # noqa: E402


# Create directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.IMAGE_DIR, exist_ok=True)

app = FastAPI(
    title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with proper origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(images.router, prefix=f"{settings.API_V1_STR}/images", tags=["images"])
app.include_router(gallery.router, prefix=f"{settings.API_V1_STR}/gallery", tags=["gallery"])
app.include_router(metadata_router.router, prefix=f"{settings.API_V1_STR}/metadata", tags=["metadata"])
app.include_router(env.router, prefix=f"{settings.API_V1_STR}", tags=["env"])


@app.get("/")
def read_root():
    return {"message": "Welcome to AI Content Lab API"}


@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
