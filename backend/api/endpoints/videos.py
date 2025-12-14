import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
    Depends,
)
from fastapi.responses import FileResponse, StreamingResponse

from backend.core import llm_client, async_llm_client, sora_client, video_sas_token
from backend.core.analyze import VideoAnalyzer, VideoExtractor
from backend.core.config import settings
from backend.core.instructions import (
    analyze_video_system_message,
    filename_system_message,
    video_prompt_enhancement_system_message,
)
from backend.models.videos import (
    VideoFilenameGenerateRequest,
    VideoFilenameGenerateResponse,
    VideoAnalyzeRequest,
    VideoAnalyzeResponse,
    VideoGenerationJobResponse,
    VideoGenerationRequest,
    VideoGenerationWithAnalysisRequest,
    VideoGenerationWithAnalysisResponse,
    VideoPromptEnhancementRequest,
    VideoPromptEnhancementResponse,
    AudioGenerationSettings,
    CameoReference,
    CameoUploadRequest,
    RemixVideoRequest,
)
from backend.core.cosmos_client import CosmosDBService


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_cosmos_service() -> Optional[CosmosDBService]:
    """Dependency to get Cosmos DB service instance (optional)"""
    try:
        # Check if we have either managed identity or key-based auth configured
        if settings.AZURE_COSMOS_DB_ENDPOINT and (
            settings.USE_MANAGED_IDENTITY or settings.AZURE_COSMOS_DB_KEY
        ):
            return CosmosDBService()
        return None
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Cosmos DB service unavailable: {e}")
        return None


# Log video directory setting
logger.info(f"Video directory: {settings.VIDEO_DIR}")

# Check if clients are available
if sora_client is None:
    logger.error(
        "Sora client is not available. API endpoints may not function properly."
    )
if llm_client is None:
    logger.error(
        "LLM client is not available. API endpoints may not function properly."
    )


router = APIRouter()


# --- SSE Helper Functions ---

def sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# --- /videos API Endpoints ---


@router.post("/jobs", response_model=VideoGenerationJobResponse)
async def create_video_generation_job(
    prompt: str = Form(...),
    n_seconds: int = Form(10),
    height: int = Form(720),
    width: int = Form(1280),
    folder_path: str = Form(""),
    analyze_video: bool = Form(False),
    # NEW: Optional image files
    images: Optional[List[UploadFile]] = File(None),
    # Sora 2 NEW: Audio generation
    audio: Optional[bool] = Form(None),
    audio_language: Optional[str] = Form(None),
    # Sora 2 NEW: Cameo reference
    cameo: Optional[str] = Form(None),
    # Sora 2 NEW: Remix video ID
    remix_video_id: Optional[str] = Form(None)
):
    """
    Enhanced to support Sora 2 features:
    - Text-only and image+text video generation
    - Audio generation with synchronized speech and sound effects
    - Cameo personalized videos
    - Video-to-video remixing
    """
    try:
        # Ensure Sora client is available
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable. Please check your environment configuration.",
            )

        # Process images if provided
        processed_images = []
        image_filenames = []
        
        if images:
            for idx, image_file in enumerate(images):
                # Read image content
                image_content = await image_file.read()

                # Validate file size (25MB limit)
                if len(image_content) > 25 * 1024 * 1024:
                    raise HTTPException(
                        400, f"Image {idx+1} exceeds 25MB limit")

                # Validate file type
                if not image_file.content_type or not image_file.content_type.startswith('image/'):
                    raise HTTPException(
                        400, f"File {idx+1} is not a valid image")

                processed_images.append(image_content)
                image_filenames.append(
                    image_file.filename or f"image_{idx+1}.jpg")
        
        # Note: Sora 2 automatically includes audio, no parameter needed
        # Remix should use the separate /remix endpoint
        # Cameo not supported in current Sora 2 API
        
        # Create job using appropriate method (async)
        if processed_images:
            # Use image+text method (Sora 2 supports single input_reference)
            job = await sora_client.create_video_generation_job_with_images(
                prompt=prompt,
                images=processed_images,
                image_filenames=image_filenames,
                n_seconds=n_seconds,
                height=height,
                width=width
            )
        else:
            # Use text-only method
            job = await sora_client.create_video_generation_job(
                prompt=prompt,
                n_seconds=n_seconds,
                height=height,
                width=width
            )
        
        # Create response with enhanced metadata (Sora 2)
        response_data = {
            **job,
            # Add metadata about images
            "has_source_images": bool(processed_images),
            "image_count": len(processed_images) if processed_images else 0,
            "folder_path": folder_path,
            "analyze_video": analyze_video,
            # Sora 2 always includes audio
            "has_audio": True
        }
        
        return VideoGenerationJobResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error creating video job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=VideoGenerationJobResponse)
async def get_video_generation_job(job_id: str):
    try:
        # Ensure Sora client is available
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable. Please check your environment configuration.",
            )

        job = await sora_client.get_video_generation_job(job_id)
        return VideoGenerationJobResponse(**job)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs", response_model=List[VideoGenerationJobResponse])
async def list_video_generation_jobs(limit: int = Query(50, ge=1, le=100)):
    try:
        # Ensure Sora client is available
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable. Please check your environment configuration.",
            )

        jobs = await sora_client.list_video_generation_jobs(limit=limit)
        return [VideoGenerationJobResponse(**job) for job in jobs.get("data", [])]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def delete_video_generation_job(job_id: str):
    try:
        # Ensure Sora client is available
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable. Please check your environment configuration.",
            )

        status_code = await sora_client.delete_video_generation_job(job_id)
        return {"deleted": status_code == 204, "job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/jobs/failed")
async def delete_failed_video_generation_jobs():
    try:
        # Ensure Sora client is available
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable. Please check your environment configuration.",
            )

        jobs = await sora_client.list_video_generation_jobs(limit=50)
        deleted = []
        for job in jobs.get("data", []):
            if job.get("status") == "failed":
                try:
                    await sora_client.delete_video_generation_job(job["id"])
                    deleted.append(job["id"])
                except Exception:
                    pass
        return {"deleted_failed_jobs": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-with-analysis/stream")
async def stream_video_generation_with_analysis(
    prompt: str = Form(...),
    n_seconds: int = Form(10),
    height: int = Form(720),
    width: int = Form(1280),
    analyze_video: bool = Form(True),
    folder_path: str = Form(""),
    metadata: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    SSE streaming endpoint for video generation with real-time progress updates.
    Non-blocking - uses asyncio.sleep() instead of time.sleep().
    """
    async def event_generator():
        try:
            # Validate services
            if sora_client is None:
                yield sse_event("error", {"error": "Video generation service is currently unavailable."})
                return

            if analyze_video and llm_client is None:
                yield sse_event("error", {"error": "LLM service is currently unavailable for video analysis."})
                return

            # Parse optional metadata JSON
            metadata_dict = None
            if metadata:
                try:
                    metadata_dict = json.loads(metadata)
                except Exception:
                    metadata_dict = None

            selected_folder = folder_path or (
                metadata_dict.get("folder") if metadata_dict else "")

            # Process images if provided
            processed_images: List[bytes] = []
            image_filenames: List[str] = []
            if images:
                for idx, image_file in enumerate(images):
                    content = await image_file.read()
                    if len(content) > 25 * 1024 * 1024:
                        yield sse_event("error", {"error": f"Image {idx+1} exceeds 25MB limit"})
                        return
                    if not image_file.content_type or not image_file.content_type.startswith("image/"):
                        yield sse_event("error", {"error": f"File {idx+1} is not a valid image"})
                        return
                    processed_images.append(content)
                    image_filenames.append(
                        image_file.filename or f"image_{idx+1}.jpg")

            # Create job
            yield sse_event("status", {"step": "creating_job", "message": "Creating video generation job..."})

            if processed_images:
                job = await sora_client.create_video_generation_job_with_images(
                    prompt=prompt,
                    images=processed_images,
                    image_filenames=image_filenames,
                    n_seconds=n_seconds,
                    height=height,
                    width=width
                )
            else:
                job = await sora_client.create_video_generation_job(
                    prompt=prompt,
                    n_seconds=n_seconds,
                    height=height,
                    width=width
                )

            job_response = VideoGenerationJobResponse(**job)
            yield sse_event("created", {"job_id": job_response.id, "status": job_response.status})

            # Poll for completion with progress updates (non-blocking!)
            max_wait_time = 300  # 5 minutes
            poll_interval = 3  # Check every 3 seconds
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                current_job = await sora_client.get_video_generation_job(job_response.id)
                job_response = VideoGenerationJobResponse(**current_job)

                yield sse_event("progress", {
                    "status": job_response.status,
                    "progress": current_job.get("progress", 0),
                    "elapsed": elapsed_time
                })

                if job_response.status == "succeeded":
                    logger.info(
                        f"Job {job_response.id} completed successfully")
                    break

                if job_response.status == "failed":
                    yield sse_event("error", {"error": f"Video generation failed: {job_response.failure_reason}"})
                    return

                await asyncio.sleep(poll_interval)  # Non-blocking!
                elapsed_time += poll_interval

            if job_response.status != "succeeded":
                yield sse_event("error", {"error": "Video generation timed out. Please try again."})
                return

            # Process completed video
            analysis_results = None
            if analyze_video and job_response.generations:
                import tempfile
                from azure.storage.blob import ContentSettings
                from backend.core.azure_storage import AzureBlobStorageService

                analysis_results = []

                for generation in job_response.generations:
                    generation_id = generation.get("id")
                    if not generation_id:
                        continue

                    # Download video
                    yield sse_event("processing", {"step": "downloading", "generation_id": generation_id})

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                        temp_file_path = temp_file.name

                    try:
                        downloaded_path = await sora_client.get_video_generation_video_content(
                            generation_id,
                            os.path.basename(temp_file_path),
                            os.path.dirname(temp_file_path),
                        )

                        # Analyze video
                        yield sse_event("processing", {"step": "analyzing", "generation_id": generation_id})

                        # Run video analysis in thread pool to not block
                        video_extractor = VideoExtractor(downloaded_path)
                        frames = await asyncio.to_thread(video_extractor.extract_video_frames, interval=2)

                        video_analyzer = VideoAnalyzer(
                            llm_client, settings.LLM_DEPLOYMENT)
                        insights = await asyncio.to_thread(
                            video_analyzer.video_chat,
                            frames,
                            system_message=analyze_video_system_message
                        )

                        analysis_result = VideoAnalyzeResponse(
                            summary=insights.get("summary", ""),
                            products=insights.get("products", ""),
                            tags=insights.get("tags", []),
                            feedback=insights.get("feedback", ""),
                        )
                        analysis_results.append(analysis_result)

                        # Upload to gallery
                        yield sse_event("processing", {"step": "uploading", "generation_id": generation_id})

                        azure_service = AzureBlobStorageService()
                        base_filename = generation.get(
                            "filename") or f"{re.sub(r'[^a-zA-Z0-9_-]', '_', prompt.strip()[:50])}_{generation_id}.mp4"
                        final_filename = base_filename
                        normalized_folder = ""

                        if selected_folder and selected_folder != "root":
                            normalized_folder = azure_service.normalize_folder_path(
                                selected_folder)
                            final_filename = f"{normalized_folder}{base_filename}"

                        container_client = azure_service.blob_service_client.get_container_client(
                            "videos")
                        blob_client = container_client.get_blob_client(
                            final_filename)

                        # Build upload metadata
                        analysis_data = {
                            "summary": analysis_result.summary,
                            "products": analysis_result.products,
                            "tags": analysis_result.tags,
                            "feedback": analysis_result.feedback,
                            "analyzed_at": datetime.now().isoformat(),
                        }
                        upload_metadata = {
                            "generation_id": generation_id,
                            "prompt": prompt,
                            "analysis": analysis_data,
                            "has_analysis": True,
                            "upload_date": datetime.now().isoformat(),
                        }
                        if selected_folder and selected_folder != "root":
                            upload_metadata["folder_path"] = normalized_folder

                        processed_metadata = {}
                        for k, v in upload_metadata.items():
                            if v is not None:
                                processed_metadata[k] = azure_service._preprocess_metadata_value(
                                    str(v))

                        def _sync_upload_blob() -> None:
                            with open(downloaded_path, "rb") as video_file:
                                blob_client.upload_blob(
                                    data=video_file,
                                    content_settings=ContentSettings(
                                        content_type="video/mp4"),
                                    metadata=processed_metadata,
                                    overwrite=True,
                                )

                        await asyncio.to_thread(_sync_upload_blob)

                        blob_url = blob_client.url

                        # Create Cosmos DB metadata record if available
                        if cosmos_service:
                            try:
                                asset_id = final_filename.split(
                                    ".")[0].split("/")[-1]
                                video_info = os.stat(downloaded_path)
                                cosmos_metadata = {
                                    "id": asset_id,
                                    "media_type": "video",
                                    "blob_name": final_filename,
                                    "container": "videos",
                                    "url": blob_url,
                                    "filename": base_filename,
                                    "size": video_info.st_size,
                                    "content_type": "video/mp4",
                                    "folder_path": normalized_folder,
                                    "prompt": prompt,
                                    "model": "sora",
                                    "generation_id": generation_id,
                                    "analysis": analysis_data,
                                    "has_analysis": True,
                                    "duration": n_seconds,
                                    "resolution": f"{width}x{height}",
                                    "custom_metadata": {
                                        "analyzed": "true",
                                        "job_id": job_response.id,
                                    },
                                }
                                await asyncio.to_thread(
                                    cosmos_service.create_asset_metadata,
                                    cosmos_metadata,
                                )
                            except Exception as cosmos_error:
                                logger.error(
                                    f"Failed to create Cosmos DB metadata: {cosmos_error}")

                    finally:
                        try:
                            if os.path.exists(temp_file_path):
                                os.unlink(temp_file_path)
                            if "downloaded_path" in locals() and os.path.exists(downloaded_path):
                                os.unlink(downloaded_path)
                        except Exception:
                            pass

            # Send completion event
            yield sse_event("complete", {
                "job": job_response.dict() if hasattr(job_response, 'dict') else dict(job_response),
                "analysis_results": [ar.dict() if hasattr(ar, 'dict') else dict(ar) for ar in (analysis_results or [])],
            })

        except Exception as e:
            logger.error(f"Error in SSE stream: {str(e)}", exc_info=True)
            yield sse_event("error", {"error": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post(
    "/generate-with-analysis/upload", response_model=VideoGenerationWithAnalysisResponse
)
async def create_video_generation_with_analysis_upload(
    prompt: str = Form(...),
    n_seconds: int = Form(10),
    height: int = Form(720),
    width: int = Form(1280),
    analyze_video: bool = Form(True),
    folder_path: str = Form(""),
    metadata: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    Unified endpoint: create a video generation job (with or without source images),
    wait for completion, optionally analyze, upload to gallery, and create metadata records.

    This endpoint is non-blocking - uses asyncio.sleep() instead of time.sleep().
    For real-time progress updates, use the /generate-with-analysis/stream endpoint instead.
    """
    import tempfile
    from azure.storage.blob import ContentSettings
    from backend.core.azure_storage import AzureBlobStorageService

    try:
        logger.info(
            f"Cosmos DB service available: {cosmos_service is not None}")
        if sora_client is None:
            raise HTTPException(
                status_code=503, detail="Video generation service is currently unavailable.")
        if analyze_video and llm_client is None:
            raise HTTPException(
                status_code=503, detail="LLM service is currently unavailable for video analysis.")

        # Parse optional metadata JSON for folder or other decorations
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except Exception:
                metadata_dict = None

        # Prefer explicit folder_path; fallback to metadata.folder
        selected_folder = folder_path or (
            metadata_dict.get("folder") if metadata_dict else "")

        # Prepare optional images
        processed_images: List[bytes] = []
        image_filenames: List[str] = []
        if images:
            for idx, image_file in enumerate(images):
                content = await image_file.read()
                if len(content) > 25 * 1024 * 1024:
                    raise HTTPException(
                        400, f"Image {idx+1} exceeds 25MB limit")
                if not image_file.content_type or not image_file.content_type.startswith("image/"):
                    raise HTTPException(
                        400, f"File {idx+1} is not a valid image")
                processed_images.append(content)
                image_filenames.append(
                    image_file.filename or f"image_{idx+1}.jpg")

        # Create job with or without images (async)
        if processed_images:
            job = await sora_client.create_video_generation_job_with_images(
                prompt=prompt,
                images=processed_images,
                image_filenames=image_filenames,
                n_seconds=n_seconds,
                height=height,
                width=width
            )
        else:
            job = await sora_client.create_video_generation_job(
                prompt=prompt,
                n_seconds=n_seconds,
                height=height,
                width=width
            )

        job_response = VideoGenerationJobResponse(**job)
        logger.info(
            f"Created job {job_response.id}, waiting for completion...")

        # Poll job until completion (non-blocking!)
        max_wait_time = 300
        poll_interval = 5
        elapsed_time = 0
        while elapsed_time < max_wait_time:
            current_job = await sora_client.get_video_generation_job(job_response.id)
            job_response = VideoGenerationJobResponse(**current_job)
            if job_response.status == "succeeded":
                logger.info(f"Job {job_response.id} completed successfully")
                break
            if job_response.status == "failed":
                raise HTTPException(
                    status_code=500, detail=f"Video generation failed: {job_response.failure_reason}")

            await asyncio.sleep(poll_interval)  # Non-blocking!
            elapsed_time += poll_interval

        if job_response.status != "succeeded":
            raise HTTPException(
                status_code=408, detail="Video generation timed out. Please try again.")

        analysis_results = None
        if analyze_video and job_response.generations:
            analysis_results = []
            for generation in job_response.generations:
                generation_id = generation.get("id")
                if not generation_id:
                    continue
                # Download generation video to temp
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                    temp_file_path = temp_file.name
                try:
                    downloaded_path = await sora_client.get_video_generation_video_content(
                        generation_id,
                        os.path.basename(temp_file_path),
                        os.path.dirname(temp_file_path),
                    )

                    # Extract frames and analyze (run in thread pool to not block)
                    video_extractor = VideoExtractor(downloaded_path)
                    frames = await asyncio.to_thread(video_extractor.extract_video_frames, interval=2)

                    video_analyzer = VideoAnalyzer(
                        llm_client, settings.LLM_DEPLOYMENT)
                    insights = await asyncio.to_thread(
                        video_analyzer.video_chat,
                        frames,
                        system_message=analyze_video_system_message
                    )

                    analysis_result = VideoAnalyzeResponse(
                        summary=insights.get("summary", ""),
                        products=insights.get("products", ""),
                        tags=insights.get("tags", []),
                        feedback=insights.get("feedback", ""),
                    )
                    analysis_results.append(analysis_result)

                    # Upload to gallery with metadata
                    azure_service = AzureBlobStorageService()
                    base_filename = generation.get(
                        "filename") or f"{re.sub(r'[^a-zA-Z0-9_-]', '_', prompt.strip()[:50])}_{generation_id}.mp4"
                    final_filename = base_filename
                    normalized_folder = ""
                    if selected_folder and selected_folder != "root":
                        normalized_folder = azure_service.normalize_folder_path(
                            selected_folder)
                        final_filename = f"{normalized_folder}{base_filename}"

                    container_client = azure_service.blob_service_client.get_container_client(
                        "videos")
                    blob_client = container_client.get_blob_client(
                        final_filename)

                    # Build upload metadata
                    analysis_data = {
                        "summary": analysis_result.summary,
                        "products": analysis_result.products,
                        "tags": analysis_result.tags,
                        "feedback": analysis_result.feedback,
                        "analyzed_at": datetime.now().isoformat(),
                    }
                    upload_metadata = {
                        "generation_id": generation_id,
                        "prompt": prompt,
                        "analysis": analysis_data,
                        "has_analysis": True,
                        "upload_date": datetime.now().isoformat(),
                    }
                    if selected_folder and selected_folder != "root":
                        upload_metadata["folder_path"] = normalized_folder

                    processed_metadata = {}
                    for k, v in upload_metadata.items():
                        if v is not None:
                            processed_metadata[k] = azure_service._preprocess_metadata_value(
                                str(v))

                    def _sync_upload_blob() -> None:
                        with open(downloaded_path, "rb") as video_file:
                            blob_client.upload_blob(
                                data=video_file,
                                content_settings=ContentSettings(
                                    content_type="video/mp4"),
                                metadata=processed_metadata,
                                overwrite=True,
                            )

                    await asyncio.to_thread(_sync_upload_blob)

                    blob_url = blob_client.url

                    # Create Cosmos DB metadata record if available
                    if cosmos_service:
                        try:
                            asset_id = final_filename.split(
                                ".")[0].split("/")[-1]
                            video_info = os.stat(downloaded_path)
                            cosmos_metadata = {
                                "id": asset_id,
                                "media_type": "video",
                                "blob_name": final_filename,
                                "container": "videos",
                                "url": blob_url,
                                "filename": base_filename,
                                "size": video_info.st_size,
                                "content_type": "video/mp4",
                                "folder_path": normalized_folder,
                                "prompt": prompt,
                                "model": "sora",
                                "generation_id": generation_id,
                                "analysis": analysis_data,
                                "has_analysis": True,
                                "duration": n_seconds,
                                "resolution": f"{width}x{height}",
                                "custom_metadata": {
                                    "analyzed": "true",
                                    "job_id": job_response.id,
                                },
                            }
                            await asyncio.to_thread(
                                cosmos_service.create_asset_metadata,
                                cosmos_metadata,
                            )
                        except Exception as cosmos_error:
                            logger.error(
                                f"Failed to create Cosmos DB metadata: {cosmos_error}")

                finally:
                    try:
                        if os.path.exists(temp_file_path):
                            os.unlink(temp_file_path)
                        if "downloaded_path" in locals() and os.path.exists(downloaded_path):
                            os.unlink(downloaded_path)
                    except Exception:
                        pass

        return VideoGenerationWithAnalysisResponse(
            job=job_response,
            analysis_results=analysis_results,
            upload_results=None,
        )
    except Exception as e:
        logger.error(
            f"Error in unified upload endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/generate-with-analysis", response_model=VideoGenerationWithAnalysisResponse
)
async def create_video_generation_with_analysis(
    req: VideoGenerationWithAnalysisRequest,
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """
    Create a video generation job and optionally analyze the results
    Enhanced with Cosmos DB metadata storage.

    This endpoint is non-blocking - uses asyncio.sleep() instead of time.sleep().
    For real-time progress updates, use the /generate-with-analysis/stream endpoint instead.
    """
    import tempfile

    try:
        # Log service availability for debugging
        logger.info(
            f"Cosmos DB service available: {cosmos_service is not None}")
        logger.info(f"Cosmos DB config - Endpoint: {settings.AZURE_COSMOS_DB_ENDPOINT is not None}, "
                   f"Use Managed Identity: {settings.USE_MANAGED_IDENTITY}, "
                   f"Has Key: {settings.AZURE_COSMOS_DB_KEY is not None}")
        if cosmos_service:
            logger.info(
                "Cosmos DB service initialized successfully for video generation")

        # Ensure required clients are available
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable.",
            )

        if req.analyze_video and llm_client is None:
            raise HTTPException(
                status_code=503,
                detail="LLM service is currently unavailable for video analysis.",
            )

        # Step 1: Create the video generation job (async)
        logger.info(f"Creating video generation job with prompt: {req.prompt}")
        job = await sora_client.create_video_generation_job(
            prompt=req.prompt,
            n_seconds=req.n_seconds,
            height=req.height,
            width=req.width
        )

        job_response = VideoGenerationJobResponse(**job)
        logger.info(
            f"Created job {job_response.id}, waiting for completion...")

        # Step 2: Poll for job completion (non-blocking!)
        max_wait_time = 300  # 5 minutes max wait
        poll_interval = 5  # Check every 5 seconds
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            current_job = await sora_client.get_video_generation_job(job_response.id)
            job_response = VideoGenerationJobResponse(**current_job)

            if job_response.status == "succeeded":
                logger.info(f"Job {job_response.id} completed successfully")
                break
            elif job_response.status == "failed":
                raise HTTPException(
                    status_code=500,
                    detail=f"Video generation failed: {job_response.failure_reason}",
                )

            await asyncio.sleep(poll_interval)  # Non-blocking!
            elapsed_time += poll_interval

        if job_response.status != "succeeded":
            raise HTTPException(
                status_code=408, detail="Video generation timed out. Please try again."
            )

        analysis_results = None

        # Step 3: Analyze videos if requested
        if req.analyze_video and job_response.generations:
            logger.info(
                f"Starting analysis for {len(job_response.generations)} generated videos")
            analysis_results = []

            for generation in job_response.generations:
                try:
                    generation_id = generation.get("id")
                    if not generation_id:
                        logger.warning(
                            "Generation missing ID, skipping analysis")
                        continue

                    logger.info(
                        f"Downloading video content for generation {generation_id}")

                    # Download video directly from Sora to a temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                        temp_file_path = temp_file.name

                    try:
                        downloaded_path = await sora_client.get_video_generation_video_content(
                                generation_id,
                                os.path.basename(temp_file_path),
                                os.path.dirname(temp_file_path),
                        )

                        logger.info(
                            f"Video downloaded directly from Sora to: {downloaded_path}")

                        # Extract frames and analyze (run in thread pool)
                        video_extractor = VideoExtractor(downloaded_path)
                        frames = await asyncio.to_thread(video_extractor.extract_video_frames, interval=2)

                        video_analyzer = VideoAnalyzer(
                            llm_client, settings.LLM_DEPLOYMENT)
                        insights = await asyncio.to_thread(
                            video_analyzer.video_chat,
                            frames,
                            system_message=analyze_video_system_message
                        )

                        analysis_result = VideoAnalyzeResponse(
                            summary=insights.get("summary", ""),
                            products=insights.get("products", ""),
                            tags=insights.get("tags", []),
                            feedback=insights.get("feedback", ""),
                        )

                        analysis_results.append(analysis_result)
                        logger.info(
                            f"Analysis completed for generation {generation_id}")

                        # Upload the video to Azure Blob Storage for gallery
                        try:
                            from backend.core.azure_storage import AzureBlobStorageService
                            from azure.storage.blob import ContentSettings

                            azure_service = AzureBlobStorageService()

                            # Generate proper filename using the dedicated API
                            try:
                                filename_req = VideoFilenameGenerateRequest(
                                    prompt=req.prompt,
                                    gen_id=generation_id,
                                    extension=".mp4",
                                )
                                filename_response = generate_video_filename(
                                    filename_req)
                                base_filename = filename_response.filename
                            except Exception as filename_error:
                                logger.warning(
                                    f"Failed to generate filename using API: {filename_error}")
                                sanitized_prompt = re.sub(
                                    r"[^a-zA-Z0-9_-]", "_", req.prompt.strip()[:50])
                                base_filename = f"{sanitized_prompt}_{generation_id}.mp4"

                            # Extract folder path from request metadata and normalize it
                            folder_path = req.metadata.get(
                                "folder") if req.metadata else None
                            final_filename = base_filename

                            if folder_path and folder_path != "root":
                                normalized_folder = azure_service.normalize_folder_path(
                                    folder_path)
                                final_filename = f"{normalized_folder}{base_filename}"
                                logger.info(
                                    f"Uploading video to folder: {normalized_folder}")
                            else:
                                logger.info(
                                    "Uploading video to root directory")
                                normalized_folder = ""

                            # Upload to Azure Blob Storage
                            container_client = azure_service.blob_service_client.get_container_client(
                                "videos")
                            blob_client = container_client.get_blob_client(
                                final_filename)

                            # Prepare metadata for blob storage with nested analysis structure
                            analysis_data = {
                                "summary": analysis_result.summary,
                                "products": analysis_result.products,
                                "tags": analysis_result.tags,
                                "feedback": analysis_result.feedback,
                                "analyzed_at": datetime.now().isoformat(),
                            }
                            
                            upload_metadata = {
                                "generation_id": generation_id,
                                "prompt": req.prompt,
                                "analysis": analysis_data,
                                "has_analysis": True,
                                "upload_date": datetime.now().isoformat(),
                            }

                            if folder_path and folder_path != "root":
                                upload_metadata["folder_path"] = azure_service.normalize_folder_path(
                                    folder_path)

                            # Preprocess metadata values for Azure compatibility
                            processed_metadata = {}
                            for k, v in upload_metadata.items():
                                if v is not None:
                                    processed_metadata[k] = azure_service._preprocess_metadata_value(
                                        str(v))

                            # Read the file and upload with metadata
                            with open(downloaded_path, "rb") as video_file:
                                blob_client.upload_blob(
                                    data=video_file,
                                    content_settings=ContentSettings(
                                        content_type="video/mp4"),
                                    metadata=processed_metadata,
                                    overwrite=True,
                                )

                            blob_url = blob_client.url
                            logger.info(
                                f"Uploaded video to gallery: {blob_url}")

                            # Create metadata record in Cosmos DB if available
                            if cosmos_service:
                                try:
                                    asset_id = final_filename.split(
                                        ".")[0].split("/")[-1]
                                    video_info = os.stat(downloaded_path)

                                    cosmos_metadata = {
                                        "id": asset_id,
                                        "media_type": "video",
                                        "blob_name": final_filename,
                                        "container": "videos",
                                        "url": blob_url,
                                        "filename": base_filename,
                                        "size": video_info.st_size,
                                        "content_type": "video/mp4",
                                        "folder_path": normalized_folder if folder_path and folder_path != "root" else "",
                                        "prompt": req.prompt,
                                        "model": "sora",
                                        "generation_id": generation_id,
                                        "analysis": {
                                            "summary": analysis_result.summary,
                                            "products": analysis_result.products,
                                            "tags": analysis_result.tags,
                                            "feedback": analysis_result.feedback,
                                            "analyzed_at": datetime.now().isoformat(),
                                        },
                                        "has_analysis": True,
                                        "duration": req.n_seconds,
                                        "resolution": f"{req.width}x{req.height}",
                                        "custom_metadata": {
                                            "analyzed": "true",
                                            "job_id": job_response.id,
                                        },
                                    }

                                    logger.info(
                                        f"Attempting to create Cosmos DB metadata for video: {asset_id}")
                                    await asyncio.to_thread(
                                        cosmos_service.create_asset_metadata,
                                        cosmos_metadata,
                                    )
                                    logger.info(
                                        f"Successfully created Cosmos DB metadata for video: {asset_id}")
                                except Exception as cosmos_error:
                                    logger.error(
                                        f"Failed to create Cosmos DB metadata for video {asset_id}: {cosmos_error}")
                                    import traceback
                                    logger.error(
                                        f"Cosmos DB error traceback: {traceback.format_exc()}")
                            else:
                                logger.warning(
                                    f"Cosmos DB service not available - skipping metadata creation for video {generation_id}")

                        except Exception as upload_error:
                            logger.warning(
                                f"Failed to upload video to gallery: {upload_error}")

                    finally:
                        # Clean up temporary files
                        try:
                            if os.path.exists(temp_file_path):
                                os.unlink(temp_file_path)
                            if "downloaded_path" in locals() and os.path.exists(downloaded_path):
                                os.unlink(downloaded_path)
                            logger.info("Cleaned up temporary files")
                        except Exception as cleanup_error:
                            logger.warning(
                                f"Failed to clean up temporary files: {cleanup_error}")

                except Exception as analysis_error:
                    logger.error(
                        f"Failed to analyze generation {generation_id}: {analysis_error}")
                    continue

        return VideoGenerationWithAnalysisResponse(
            job=job_response, analysis_results=analysis_results, upload_results=None
        )

    except Exception as e:
        logger.error(
            f"Error in unified video generation with analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generations/{generation_id}/content", status_code=status.HTTP_200_OK)
async def download_generation_content(
    generation_id: str,
    file_name: str,
    target_folder: Optional[str] = None,
    as_gif: bool = False,
):
    """
    Download video or GIF content for a specific generation.

    Args:
        generation_id: The ID of the generation
        file_name: Name to save the file as
        target_folder: Optional folder to save to (defaults to settings.VIDEO_DIR or 'gifs')
        as_gif: Whether to download as GIF instead of MP4

    Returns:
        FileResponse with the requested content
    """
    try:
        # Ensure Sora client is available
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable. Please check your environment configuration.",
            )

        # Use settings from config if target_folder not provided
        if not target_folder:
            target_folder = settings.VIDEO_DIR if not as_gif else "gifs"

        logger.info(
            f"Downloading {'GIF' if as_gif else 'video'} content for generation {generation_id}")

        if as_gif:
            file_path = await sora_client.get_video_generation_gif_content(
                generation_id, file_name, target_folder
            )
        else:
            file_path = await sora_client.get_video_generation_video_content(
                generation_id, file_name, target_folder
            )

        # Verify the file was downloaded successfully
        if not os.path.isfile(file_path):
            raise FileNotFoundError(
                f"Downloaded file not found at {file_path}")

        logger.info(f"Successfully downloaded file. Returning: {file_path}")

        # Use FileResponse to return the file
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="image/gif" if as_gif else "video/mp4",
        )

    except Exception as e:
        logger.error(f"Error downloading content: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading content: {str(e)}",
        )


@router.post("/analyze", response_model=VideoAnalyzeResponse)
async def analyze_video(req: VideoAnalyzeRequest):
    """
    Analyze a video by extracting frames and generating insights using an LLM.

    Args:
        video_path: Video path on Azure Blob Storage. Supports a full URL with or without a SAS token.

    Returns:
        Response containing summary, products, tags, and feedback generated by the LLM.
    """
    import tempfile
    import httpx

    try:
        file_path = req.video_path

        # check if the path is a valid Azure blob storage path
        pattern = r"^https://[a-z0-9]+\.blob\.core\.windows\.net/[a-z0-9]+/.+"
        match = re.match(pattern, file_path)

        if not match:
            raise ValueError("Invalid Azure blob storage path")
        else:
            # check if the path contains a SAS token
            if "?" not in file_path:
                file_path += f"?{video_sas_token}"

        # Download the video file to a temporary location with retry logic
        logger.info(f"Downloading video from Azure Blob Storage: {file_path}")

        # Retry logic for Azure Blob Storage propagation delays
        max_retries = 3
        retry_delay = 5  # seconds

        temp_file_path = ""
        last_http_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            for attempt in range(max_retries):
                try:
                    async with client.stream("GET", file_path) as response:
                        response.raise_for_status()

                        # Create a temporary file to store the downloaded video
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
                            temp_file_path = temp_file.name
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                if chunk:
                                    temp_file.write(chunk)
                        break  # Success
                except httpx.HTTPStatusError as e:
                    last_http_error = e
                    status_code = e.response.status_code
                    if status_code == 404 and attempt < max_retries - 1:
                        logger.warning(
                            f"Video not found (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay} seconds..."
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                    raise
                except Exception as e:
                    last_http_error = e
                    raise

        logger.info(f"Video downloaded to temporary file: {temp_file_path}")

        try:
            # extract frames from the video each 2 seconds using the local file
            video_extractor = VideoExtractor(temp_file_path)
            frames = await asyncio.to_thread(video_extractor.extract_video_frames, interval=2)

            video_analyzer = VideoAnalyzer(llm_client, settings.LLM_DEPLOYMENT)
            insights = await asyncio.to_thread(
                video_analyzer.video_chat,
                frames,
                system_message=analyze_video_system_message
            )

            summary = insights.get("summary")
            products = insights.get("products")
            tags = insights.get("tags")
            feedback = insights.get("feedback")

            return VideoAnalyzeResponse(
                summary=summary, products=products, tags=tags, feedback=feedback
            )

        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to clean up temporary file {temp_file_path}: {cleanup_error}")

    except Exception as e:
        logger.error(f"Error analyzing video: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error analyzing video. Please try again later."
        )


@router.post("/prompt/enhance", response_model=VideoPromptEnhancementResponse)
async def enhance_video_prompt(req: VideoPromptEnhancementRequest):
    """
    Improves a given text to video prompt considering best practices for the video generation model.

    Args:
        original_prompt: Original text to video prompt.

    Returns:
        enhanced_prompt: Improved text to video prompt.
    """
    try:
        # Ensure LLM client is available
        if async_llm_client is None:
            raise HTTPException(
                status_code=503,
                detail="LLM service is currently unavailable. Please check your environment configuration.",
            )

        original_prompt = req.original_prompt
        # Call the LLM to enhance the prompt (async)
        messages = [
            {"role": "system", "content": video_prompt_enhancement_system_message},
            {"role": "user", "content": original_prompt},
        ]
        response = await async_llm_client.chat.completions.create(
            messages=messages,
            model=settings.LLM_DEPLOYMENT,
            response_format={"type": "json_object"},
        )
        enhanced_prompt = json.loads(
            response.choices[0].message.content).get("prompt")
        return VideoPromptEnhancementResponse(enhanced_prompt=enhanced_prompt)

    except Exception as e:
        logger.error(f"Error enhancing video prompt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filename/generate", response_model=VideoFilenameGenerateResponse)
async def generate_video_filename(req: VideoFilenameGenerateRequest):
    """
    Creates a concise prefix for a file based on the text prompt used for creating the image or video.

    Args:
        prompt: Text prompt.
        gen_id: Optional generation ID to append for uniqueness.
        extension: Optional file extension to append (e.g., ".mp4").

    Returns:
        filename: Generated filename Example: "xbox_venice_beach_sunset_2023_12345.mp4"
    """

    try:
        # Ensure LLM client is available
        if async_llm_client is None:
            raise HTTPException(
                status_code=503,
                detail="LLM service is currently unavailable. Please check your environment configuration.",
            )

        # Validate prompt
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(
                status_code=400, detail="Prompt must not be empty.")

        # Call the LLM to generate filename (async)
        messages = [
            {"role": "system", "content": filename_system_message},
            {"role": "user", "content": req.prompt},
        ]
        response = await async_llm_client.chat.completions.create(
            messages=messages,
            model=settings.LLM_DEPLOYMENT,
            response_format={"type": "json_object"},
        )
        filename = json.loads(
            response.choices[0].message.content).get("filename_prefix")

        # Validate and sanitize filename
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=500, detail="Failed to generate a valid filename prefix."
            )
        # Remove invalid characters for most filesystems
        filename = re.sub(r"[^a-zA-Z0-9_-]", "_", filename.strip())

        # add generation id for uniqueness and extension if provided
        if req.gen_id:
            filename += f"_{req.gen_id}"
        if req.extension:
            ext = req.extension.lstrip(".")
            filename += f".{ext}"

        return VideoFilenameGenerateResponse(filename=filename)

    except Exception as e:
        logger.error(f"Error generating filename: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Sora 2 Cameo Endpoints ---

@router.post("/cameo/upload", response_model=CameoReference)
async def upload_cameo_reference(
    face_image: UploadFile = File(..., description="Face image for cameo"),
    voice_audio: Optional[UploadFile] = File(
        None, description="Optional voice audio sample")
):
    """
    Upload a cameo reference for personalized video generation (Sora 2 feature).
    Requires face image and optionally voice audio.
    """
    try:
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable."
            )
        
        # Read face image
        face_bytes = await face_image.read()
        
        # Validate file size (25MB limit per file)
        if len(face_bytes) > 25 * 1024 * 1024:
            raise HTTPException(400, "Face image exceeds 25MB limit")
        
        # Read voice audio if provided
        voice_bytes = None
        if voice_audio:
            voice_bytes = await voice_audio.read()
            if len(voice_bytes) > 25 * 1024 * 1024:
                raise HTTPException(400, "Voice audio exceeds 25MB limit")
        
        # Upload to Sora 2 API (async)
        result = await sora_client.upload_cameo_reference(face_bytes, voice_bytes)
        
        return CameoReference(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error uploading cameo reference: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cameo/references", response_model=List[CameoReference])
async def list_cameo_references(limit: int = Query(10, ge=1, le=100)):
    """
    List uploaded cameo references.
    """
    try:
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable."
            )
        
        result = await sora_client.get_cameo_references(limit=limit)
        return [CameoReference(**ref) for ref in result.get("data", [])]
        
    except Exception as e:
        logger.error(
            f"Error listing cameo references: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cameo/references/{reference_id}")
async def delete_cameo_reference(reference_id: str):
    """
    Delete a cameo reference.
    """
    try:
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable."
            )
        
        status_code = await sora_client.delete_cameo_reference(reference_id)
        return {"deleted": status_code == 204, "reference_id": reference_id}
        
    except Exception as e:
        logger.error(
            f"Error deleting cameo reference: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))


# --- Sora 2 Remix (Video-to-Video) Endpoints ---

@router.post("/remix", response_model=VideoGenerationJobResponse)
async def create_remix_job(req: RemixVideoRequest):
    """
    Create a remix job to modify an existing video (video-to-video transformation).
    This is a Sora 2 exclusive feature.
    """
    try:
        if sora_client is None:
            raise HTTPException(
                status_code=503,
                detail="Video generation service is currently unavailable."
            )
        
        # Build modifications dict
        modifications = {}
        if req.style_transfer:
            modifications["style_transfer"] = req.style_transfer
        if req.face_swap:
            modifications["cameo"] = req.face_swap
        if req.audio_override:
            modifications["audio"] = req.audio_override.dict()
        
        # Create remix job (async)
        job = await sora_client.create_remix_job(
            video_id=req.video_id,
            prompt=req.prompt,
            modifications=modifications if modifications else None
        )
        
        return VideoGenerationJobResponse(**job)
        
    except Exception as e:
        logger.error(f"Error creating remix job: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
