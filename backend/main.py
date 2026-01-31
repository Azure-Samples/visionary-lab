# Configure logging first, before other imports
from .core.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import uvicorn
from .core.config import settings
from .api.endpoints import images, metadata_router, videos, gallery, env

# Create directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.IMAGE_DIR, exist_ok=True)
os.makedirs(settings.VIDEO_DIR, exist_ok=True)

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
app.include_router(
    images.router, prefix=f"{settings.API_V1_STR}/images", tags=["images"]
)
app.include_router(
    videos.router, prefix=f"{settings.API_V1_STR}/videos", tags=["videos"]
)
app.include_router(
    gallery.router, prefix=f"{settings.API_V1_STR}/gallery", tags=["gallery"]
)
app.include_router(
    metadata_router.router, prefix=f"{settings.API_V1_STR}/metadata", tags=["metadata"]
)
app.include_router(env.router, prefix=f"{settings.API_V1_STR}", tags=["env"])
# app.include_router(organizer.router, prefix=f"{settings.API_V1_STR}/organizer", tags=["organizer"])
# app.include_router(sora.router, prefix=f"{settings.API_V1_STR}/sora", tags=["sora"])


@app.get("/")
def read_root():
    return {"message": "Welcome to AI Content Lab API"}


@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    return {"status": "ok"}


# This allows the file to be run directly with `python backend/main.py`
if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
