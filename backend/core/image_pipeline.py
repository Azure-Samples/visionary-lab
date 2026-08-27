import asyncio
import base64
import binascii
import io
import inspect
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from azure.core.exceptions import ResourceNotFoundError
from fastapi import HTTPException, UploadFile
from PIL import Image

from backend.core import get_core_clients
from backend.core.analyze import ImageAnalyzer
from backend.core.azure_storage import AzureBlobStorageService
from backend.core.config import settings
from backend.core.cosmos_client import CosmosDBService
from backend.core.instructions import analyze_image_system_message
from backend.models.images import (
    ImageEditRequest,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImagePipelineRequest,
    ImagePipelineResponse,
    ImageSaveRequest,
    ImageSaveResponse,
    PipelineAction,
    PipelineStepResult,
    TokenUsage,
    InputTokensDetails,
    validate_image_model,
    validate_image_options,
    validate_image_size,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, Dict[str, object]], Awaitable[None]]


class ImagePipelineService:
    """Service that centralises the image generation/edit/save pipeline logic."""

    def __init__(self, max_concurrent_io: Optional[int] = None) -> None:
        self._image_analyzer: Optional[ImageAnalyzer] = None
        self._image_clients: Dict[str, Any] = {}
        self._image_client_lock = asyncio.Lock()
        configured_concurrency = max_concurrent_io or getattr(
            settings, "IMAGE_JOB_CONCURRENCY", 4
        )
        self._max_concurrent_io = max(1, configured_concurrency)

    # ------------------------------------------------------------------
    # Generation / Edit helpers
    # ------------------------------------------------------------------
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """Generate images via the configured GPT Image or FLUX client."""
        try:
            client = await self._get_image_client(request.model)
            
            params: Dict[str, object] = {
                "prompt": request.prompt,
                "model": request.model,
                "n": request.n,
                "size": request.size,
            }

            # Add generation controls supported by GPT-Image-2.
            if request.quality:
                params["quality"] = request.quality
            params["background"] = request.background
            if request.output_format != "png":
                params["output_format"] = request.output_format
            if (
                request.output_format in ["webp", "jpeg"]
                and request.output_compression != 100
            ):
                params["output_compression"] = request.output_compression
            if request.moderation != "auto":
                params["moderation"] = request.moderation
            if request.user:
                params["user"] = request.user

            response = await client.generate_image(**params)
            token_usage = self._extract_token_usage(response)

            return ImageGenerationResponse(
                success=True,
                message="Refer to the imgen_model_response for details",
                imgen_model_response=response,
                token_usage=token_usage,
            )
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - delegated to HTTP response
            logger.error("Error generating image: %s", exc, exc_info=True)
            raise self._provider_http_exception(exc) from exc

    async def edit(self, request: ImageEditRequest) -> ImageGenerationResponse:
        """Edit images via the configured client using JSON payload data."""
        try:
            raw_images = (
                request.image if isinstance(request.image, list) else [request.image]
            )
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True
            ) as http_client:
                prepared_images = await asyncio.gather(
                    *(
                        self._prepare_edit_source(source, idx, http_client)
                        for idx, source in enumerate(raw_images)
                    )
                )
                prepared_mask = (
                    await self._prepare_edit_source(request.mask, 0, http_client)
                    if request.mask
                    else None
                )

            params: Dict[str, object] = {
                "prompt": request.prompt,
                "model": request.model,
                "n": request.n,
                "size": request.size,
                "image": (
                    prepared_images
                    if len(prepared_images) > 1
                    else prepared_images[0]
                ),
            }

            if prepared_mask:
                params["mask"] = prepared_mask

            # Add model-specific parameters
            if request.quality:
                params["quality"] = request.quality
            if request.output_format != "png":
                params["output_format"] = request.output_format
            if request.background != "auto":
                params["background"] = request.background
            if (
                request.output_format in ["webp", "jpeg"]
                and request.output_compression != 100
            ):
                params["output_compression"] = request.output_compression
            if request.input_fidelity and request.input_fidelity != "low":
                params["input_fidelity"] = request.input_fidelity
            if request.user:
                params["user"] = request.user

            if isinstance(request.image, list):
                image_count = len(request.image)
                if image_count > 1 and not settings.OPENAI_ORG_VERIFIED:
                    logger.warning(
                        "Using multiple reference images requires organization verification"
                    )

            client = await self._get_image_client(request.model)
            response = await client.edit_image(**params)
            token_usage = self._extract_token_usage(response)

            return ImageGenerationResponse(
                success=True,
                message="Refer to the imgen_model_response for details",
                imgen_model_response=response,
                token_usage=token_usage,
            )
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - delegated to HTTP response
            logger.error("Error editing image: %s", exc, exc_info=True)
            raise self._provider_http_exception(exc) from exc

    async def edit_with_uploads(
        self,
        *,
        prompt: str,
        model: str,
        n: int,
        size: str,
        quality: str,
        output_format: str,
        background: str,
        input_fidelity: str,
        images: List[UploadFile],
        mask: Optional[UploadFile] = None,
    ) -> ImageGenerationResponse:
        """Edit images using uploaded multipart files."""

        try:
            validate_image_model(model)
            validate_image_size(model, size)
            validate_image_options(
                model,
                quality=quality,
                output_format=output_format,
                response_format="b64_json",
                background=background,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if input_fidelity not in ["low", "high"]:
            raise HTTPException(
                status_code=400,
                detail="input_fidelity must be either 'low' or 'high'",
            )
        if not images:
            raise HTTPException(
                status_code=400,
                detail="At least one source image is required",
            )

        try:
            max_file_size_mb = settings.GPT_IMAGE_MAX_FILE_SIZE_MB
            image_files: List[Tuple[str, bytes, str]] = []
            for idx, upload in enumerate(images):
                contents = await upload.read()
                file_size_mb = len(contents) / (1024 * 1024)
                if file_size_mb >= max_file_size_mb:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Image {idx + 1} exceeds maximum size of {max_file_size_mb}MB"
                        ),
                    )
                ext = self._determine_extension(upload.content_type, contents)
                filename = upload.filename or f"source_{idx + 1}.{ext}"
                content_type = upload.content_type or f"image/{ext}"
                image_files.append((filename, contents, content_type))
                logger.debug(
                    "Prepared uploaded image %s with format %s", idx + 1, ext
                )

            mask_file: Optional[Tuple[str, bytes, str]] = None
            if mask:
                mask_contents = await mask.read()
                mask_size_mb = len(mask_contents) / (1024 * 1024)
                if mask_size_mb >= max_file_size_mb:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Mask exceeds maximum size of {max_file_size_mb}MB",
                    )
                mask_ext = self._determine_extension(
                    mask.content_type, mask_contents)
                mask_file = (
                    mask.filename or f"mask.{mask_ext}",
                    mask_contents,
                    mask.content_type or f"image/{mask_ext}",
                )

            params: Dict[str, object] = {
                "prompt": prompt,
                "model": model,
                "n": n,
                "size": size,
            }

            # Add GPT-Image-2 quality and input-fidelity controls.
            params["quality"] = quality
            if output_format != "png":
                params["output_format"] = output_format
            if background != "auto":
                params["background"] = background
            if input_fidelity != "low":
                params["input_fidelity"] = input_fidelity

            params["image"] = image_files if len(image_files) > 1 else image_files[0]
            if mask_file:
                params["mask"] = mask_file

            response = await self._invoke_edit(params, model)
            token_usage = self._extract_token_usage(response)

            return ImageGenerationResponse(
                success=True,
                message="Refer to the imgen_model_response for details",
                imgen_model_response=response,
                token_usage=token_usage,
            )
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - delegated to HTTP response
            logger.error("Error editing image upload: %s", exc, exc_info=True)
            raise self._provider_http_exception(exc) from exc

    async def save(
        self,
        request: ImageSaveRequest,
        *,
        azure_storage_service: AzureBlobStorageService,
        cosmos_service: Optional[CosmosDBService] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ImageSaveResponse:
        """Persist generated images and optionally run analysis."""

        if (
            not request.generation_response
            or not request.generation_response.imgen_model_response
        ):
            raise HTTPException(
                status_code=400,
                detail="No valid image generation response provided",
            )

        images_data = request.generation_response.imgen_model_response.get(
            "data", []
        )
        if not images_data:
            raise HTTPException(
                status_code=400,
                detail="No images found in the generation response",
            )

        if not request.save_all:
            images_data = [images_data[0]]

        combined_metadata = self._build_base_metadata(request)
        image_job_id = (
            str(request.metadata["image_job_id"])
            if request.metadata and request.metadata.get("image_job_id")
            else None
        )

        # Extract deployment metadata for tracking
        deployment_name = request.generation_response.imgen_model_response.get("_deployment_name")
        model_used = request.generation_response.imgen_model_response.get("_model")

        await self._emit_progress(
            progress_callback,
            "saving",
            {"status": "started", "total": len(images_data), "completed": 0},
        )
        semaphore = asyncio.Semaphore(self._max_concurrent_io)
        completed_saves = 0
        failed_saves = 0

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True
        ) as http_client:

            async def save_one(
                idx: int, img_data: Dict[str, object]
            ) -> Tuple[int, Dict[str, object] | None, Exception | None]:
                nonlocal completed_saves, failed_saves
                async with semaphore:
                    try:
                        img_file, filename, has_transparency = (
                            await self._prepare_image_file_async(
                                img_data, request.prompt, idx, http_client
                            )
                        )
                        if image_job_id:
                            extension = filename.rsplit(".", 1)[-1]
                            filename = self._generate_job_filename(
                                image_job_id, extension, idx
                            )

                        image_metadata = combined_metadata.copy()
                        image_metadata["image_index"] = str(idx + 1)
                        image_metadata["total_images"] = str(len(images_data))

                        upload = UploadFile(filename=filename, file=img_file)
                        try:
                            result = await azure_storage_service.upload_asset(
                                upload,
                                metadata=None,
                                folder_path=request.folder_path,
                                overwrite_existing=image_job_id is not None,
                            )

                            if cosmos_service:
                                try:
                                    await self._create_or_update_metadata(
                                        cosmos_service,
                                        result,
                                        request,
                                        has_transparency,
                                        image_metadata,
                                        deployment_name,
                                        model_used,
                                    )
                                except Exception:
                                    # The Cosmos-backed gallery is the durable
                                    # source of truth. Do not leave invisible
                                    # orphan blobs when its metadata write fails.
                                    await azure_storage_service.delete_asset_async(
                                        str(result["blob_name"]),
                                        str(result["container"]),
                                    )
                                    raise
                        finally:
                            await upload.close()

                        result["original_index"] = idx + 1
                        completed_saves += 1
                        await self._emit_progress(
                            progress_callback,
                            "saving",
                            {
                                "status": "in_progress",
                                "completed": completed_saves,
                                "failed": failed_saves,
                                "total": len(images_data),
                                "image_index": idx + 1,
                                "asset": result,
                            },
                        )
                        return idx, result, None
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        failed_saves += 1
                        await self._emit_progress(
                            progress_callback,
                            "saving",
                            {
                                "status": "in_progress",
                                "completed": completed_saves,
                                "failed": failed_saves,
                                "total": len(images_data),
                                "image_index": idx + 1,
                                "error": str(exc),
                            },
                        )
                        return idx, None, exc

            save_results = await asyncio.gather(
                *(save_one(idx, img_data) for idx, img_data in enumerate(images_data))
            )

        saved_images = [
            result
            for _, result, _ in sorted(save_results, key=lambda item: item[0])
            if result is not None
        ]
        errors = [
            error
            for _, _, error in sorted(save_results, key=lambda item: item[0])
            if error is not None
        ]
        if not saved_images and errors:
            raise errors[0]
        await self._emit_progress(
            progress_callback,
            "saving",
            {
                "status": "completed",
                "completed": len(saved_images),
                "failed": len(errors),
                "total": len(images_data),
            },
        )

        analysis_results: List[Dict[str, object]] = []
        analyzed = False

        if (
            request.analyze
            and saved_images
            and cosmos_service
        ):
            analyzed = True
            analysis_results = await self._run_analysis_on_saved_images(
                saved_images,
                cosmos_service,
                request,
                azure_storage_service=azure_storage_service,
                progress_callback=progress_callback,
            )

        return ImageSaveResponse(
            success=True,
            message=f"Saved {len(saved_images)} image(s)",
            saved_images=saved_images,
            total_saved=len(saved_images),
            prompt=request.prompt,
            analysis_results=analysis_results if analysis_results else None,
            analyzed=analyzed,
        )

    async def process_pipeline(
        self,
        pipeline_request: ImagePipelineRequest,
        *,
        azure_storage_service: Optional[AzureBlobStorageService] = None,
        cosmos_service: Optional[CosmosDBService] = None,
        source_images: Optional[List[UploadFile]] = None,
        mask: Optional[UploadFile] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ImagePipelineResponse:
        """Execute the requested pipeline flow end-to-end."""

        steps: List[PipelineStepResult] = []
        generation_response: Optional[ImageGenerationResponse] = None
        save_response: Optional[ImageSaveResponse] = None

        action_step = (
            "edit"
            if pipeline_request.action == PipelineAction.EDIT or source_images
            else "generate"
        )

        try:
            await self._emit_progress(
                progress_callback,
                "editing" if action_step == "edit" else "generating",
                {"status": "started", "total": pipeline_request.n, "completed": 0},
            )
            if action_step == "edit":
                if source_images:
                    generation_response = await self.edit_with_uploads(
                        prompt=pipeline_request.prompt,
                        model=pipeline_request.model,
                        n=pipeline_request.n,
                        size=pipeline_request.size,
                        quality=pipeline_request.quality or "high",
                        output_format=pipeline_request.output_format or "png",
                        background=pipeline_request.background or "auto",
                        input_fidelity=pipeline_request.input_fidelity or "low",
                        images=source_images,
                        mask=mask,
                    )
                else:
                    resolved_images = await self._resolve_edit_images(
                        pipeline_request,
                        azure_storage_service=azure_storage_service,
                    )
                    edit_request = ImageEditRequest(
                        prompt=pipeline_request.prompt,
                        model=pipeline_request.model,
                        n=pipeline_request.n,
                        size=pipeline_request.size,
                        response_format=pipeline_request.response_format,
                        quality=pipeline_request.quality,
                        output_format=pipeline_request.output_format,
                        output_compression=pipeline_request.output_compression,
                        background=pipeline_request.background,
                        moderation=pipeline_request.moderation,
                        user=pipeline_request.user,
                        input_fidelity=pipeline_request.input_fidelity,
                        image=resolved_images,
                        mask=pipeline_request.mask_image_url,
                    )
                    generation_response = await self.edit(edit_request)
                steps.append(
                    PipelineStepResult(
                        step="edit",
                        success=True,
                        message="Image edit completed",
                    )
                )
                await self._emit_progress(
                    progress_callback,
                    "editing",
                    {
                        "status": "completed",
                        "completed": pipeline_request.n,
                        "total": pipeline_request.n,
                    },
                )
            else:
                generation_request = ImageGenerationRequest(
                    prompt=pipeline_request.prompt,
                    model=pipeline_request.model,
                    n=pipeline_request.n,
                    size=pipeline_request.size,
                    response_format=pipeline_request.response_format,
                    quality=pipeline_request.quality,
                    output_format=pipeline_request.output_format,
                    output_compression=pipeline_request.output_compression,
                    background=pipeline_request.background,
                    moderation=pipeline_request.moderation,
                    user=pipeline_request.user,
                )
                generation_response = await self.generate(generation_request)
                steps.append(
                    PipelineStepResult(
                        step="generate",
                        success=True,
                        message="Image generation completed",
                    )
                )
                await self._emit_progress(
                    progress_callback,
                    "generating",
                    {
                        "status": "completed",
                        "completed": pipeline_request.n,
                        "total": pipeline_request.n,
                    },
                )
        except HTTPException as exc:
            await self._emit_progress(
                progress_callback,
                "editing" if action_step == "edit" else "generating",
                {"status": "failed", "error": str(exc.detail)},
            )
            steps.append(
                PipelineStepResult(
                    step=action_step,
                    success=False,
                    message=str(exc.detail),
                )
            )
            raise
        except Exception as exc:  # pragma: no cover - delegated to HTTP response
            await self._emit_progress(
                progress_callback,
                "editing" if action_step == "edit" else "generating",
                {"status": "failed", "error": str(exc)},
            )
            steps.append(
                PipelineStepResult(
                    step=action_step,
                    success=False,
                    message=str(exc),
                )
            )
            raise HTTPException(status_code=500, detail=str(exc))

        if (
            pipeline_request.save_options.enabled
            and generation_response
            and azure_storage_service
        ):
            save_request = ImageSaveRequest(
                generation_response=generation_response,
                prompt=pipeline_request.prompt,
                model=pipeline_request.model,
                size=pipeline_request.size,
                background=(
                    pipeline_request.save_options.background
                    or pipeline_request.background
                ),
                output_format=(
                    pipeline_request.save_options.output_format
                    or pipeline_request.output_format
                    or "png"
                ),
                save_all=pipeline_request.save_options.save_all,
                folder_path=pipeline_request.save_options.folder_path,
                analyze=pipeline_request.analysis_options.enabled,
                metadata=self._merge_pipeline_metadata(pipeline_request),
            )
            try:
                save_response = await self.save(
                    save_request,
                    azure_storage_service=azure_storage_service,
                    cosmos_service=cosmos_service,
                    progress_callback=progress_callback,
                )
                steps.append(
                    PipelineStepResult(
                        step="save",
                        success=True,
                        message=f"Saved {save_response.total_saved} image(s)",
                    )
                )
            except HTTPException as exc:
                await self._emit_progress(
                    progress_callback,
                    "saving",
                    {"status": "failed", "error": str(exc.detail)},
                )
                steps.append(
                    PipelineStepResult(
                        step="save",
                        success=False,
                        message=str(exc.detail),
                    )
                )
                raise
            except Exception as exc:  # pragma: no cover - delegated to HTTP response
                await self._emit_progress(
                    progress_callback,
                    "saving",
                    {"status": "failed", "error": str(exc)},
                )
                steps.append(
                    PipelineStepResult(
                        step="save",
                        success=False,
                        message=str(exc),
                    )
                )
                raise HTTPException(status_code=500, detail=str(exc)) from exc

        elif pipeline_request.analysis_options.enabled:
            steps.append(
                PipelineStepResult(
                    step="analyze",
                    success=False,
                    message="Analysis requires saved images; enable save_options",
                )
            )

        overall_success = all(step.success for step in steps)
        message = "Pipeline completed"
        if not overall_success:
            message = "Pipeline completed with issues"

        return ImagePipelineResponse(
            success=overall_success,
            message=message,
            steps=steps,
            generation=generation_response,
            save=save_response,
        )

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _provider_http_exception(exc: Exception) -> HTTPException:
        status_code = 400 if isinstance(exc, ValueError) else getattr(exc, "status_code", 500)
        if not isinstance(status_code, int) or not 400 <= status_code <= 599:
            status_code = 500
        retry_after_seconds = getattr(exc, "retry_after_seconds", None)
        if retry_after_seconds is None:
            response = getattr(exc, "response", None)
            response_headers = getattr(response, "headers", None)
            if response_headers is not None:
                from backend.core.gpt_image import parse_retry_after_seconds

                retry_after_seconds = parse_retry_after_seconds(response_headers)
        headers = (
            {"Retry-After": str(max(0, int(retry_after_seconds)))}
            if isinstance(retry_after_seconds, (int, float))
            else None
        )
        return HTTPException(
            status_code=status_code,
            detail=str(exc),
            headers=headers,
        )

    @staticmethod
    def _extract_token_usage(response: Dict[str, object]) -> Optional[TokenUsage]:
        if "usage" not in response:
            return None

        usage = response["usage"]
        input_tokens_details = None
        if isinstance(usage, dict) and "input_tokens_details" in usage:
            details = usage.get("input_tokens_details", {})
            input_tokens_details = InputTokensDetails(
                text_tokens=details.get("text_tokens", 0),
                image_tokens=details.get("image_tokens", 0),
            )

        return TokenUsage(
            total_tokens=usage.get("total_tokens", 0),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            input_tokens_details=input_tokens_details,
        )

    @staticmethod
    def _determine_extension(content_type: Optional[str], contents: bytes) -> str:
        ext = (content_type or "image/png").split("/")[-1]
        if ext not in {"jpeg", "jpg", "png", "webp"}:
            try:
                with Image.open(io.BytesIO(contents)) as pil_img:
                    ext = pil_img.format.lower() if pil_img.format else "png"
            except Exception:
                ext = "png"
        if ext == "jpg":
            ext = "jpeg"
        return ext

    async def _invoke_edit(
        self, params: Dict[str, object], model: str
    ) -> Dict[str, object]:
        client = await self._get_image_client(model)
        return await client.edit_image(**params)

    async def _get_image_client(self, model: str):
        client = self._image_clients.get(model)
        if client is not None:
            return client
        async with self._image_client_lock:
            client = self._image_clients.get(model)
            if client is None:
                from backend.core.gpt_image import GPTImageClient

                client = GPTImageClient(
                    provider=settings.MODEL_PROVIDER,
                    model=model,
                )
                self._image_clients[model] = client
            return client

    async def close(self) -> None:
        clients = list(self._image_clients.values())
        self._image_clients.clear()
        if clients:
            await asyncio.gather(
                *(client.close() for client in clients),
                return_exceptions=True,
            )

    async def _prepare_edit_source(
        self,
        source: object,
        idx: int,
        http_client: httpx.AsyncClient,
    ) -> Tuple[str, bytes, str]:
        value = str(source)
        if value.startswith(("http://", "https://")):
            response = await http_client.get(value)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to download source image: HTTP {exc.response.status_code}",
                ) from exc
            contents = response.content
            content_type = response.headers.get("content-type", "image/png").split(";", 1)[0]
            extension = self._determine_extension(content_type, contents)
            source_name = Path(urlparse(value).path).name
            filename = (
                source_name
                if Path(source_name).suffix.lower() in {".jpeg", ".jpg", ".png", ".webp"}
                else f"source_{idx + 1}.{extension}"
            )
        elif value.startswith("data:image/"):
            try:
                header, encoded = value.split(",", 1)
                contents = base64.b64decode(encoded, validate=True)
                content_type = header.split(";", 1)[0].removeprefix("data:")
            except (ValueError, binascii.Error) as exc:
                raise HTTPException(
                    status_code=400, detail="Invalid base64 image data URI"
                ) from exc
            extension = self._determine_extension(content_type, contents)
            filename = f"source_{idx + 1}.{extension}"
        else:
            path = Path(value)
            try:
                is_local_file = len(value) < 4096 and path.is_file()
            except OSError:
                is_local_file = False
            if is_local_file:
                contents = await asyncio.to_thread(path.read_bytes)
                extension = self._determine_extension(None, contents)
                filename = path.name
                content_type = f"image/{extension}"
            else:
                try:
                    contents = base64.b64decode("".join(value.split()), validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise HTTPException(
                        status_code=400,
                        detail="Image must be an accessible URL, local path, or valid base64 data",
                    ) from exc
                extension = self._determine_extension(None, contents)
                filename = f"source_{idx + 1}.{extension}"
                content_type = f"image/{extension}"

        max_bytes = settings.GPT_IMAGE_MAX_FILE_SIZE_MB * 1024 * 1024
        if len(contents) >= max_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Image {idx + 1} exceeds maximum size of "
                    f"{settings.GPT_IMAGE_MAX_FILE_SIZE_MB}MB"
                ),
            )
        return filename, contents, content_type

    async def _prepare_image_file_async(
        self,
        img_data: Dict[str, object],
        prompt: Optional[str],
        idx: int,
        http_client: httpx.AsyncClient,
    ) -> Tuple[io.BytesIO, str, Optional[bool]]:
        if "url" not in img_data:
            return await asyncio.to_thread(
                self._prepare_image_file, img_data, prompt, idx
            )

        response = await http_client.get(str(img_data["url"]))
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to download generated image: HTTP {exc.response.status_code}",
            ) from exc

        content_type = response.headers.get("content-type")
        extension = self._determine_extension(content_type, response.content)
        filename = self._generate_filename(prompt, extension, idx)
        return io.BytesIO(response.content), filename, None

    def _prepare_image_file(
        self,
        img_data: Dict[str, object],
        prompt: Optional[str],
        idx: int,
    ) -> Tuple[io.BytesIO, str, Optional[bool]]:
        img_file = io.BytesIO()
        filename = f"generated_image_{idx + 1}.png"
        has_transparency: Optional[bool] = None
        img_format = "PNG"

        if "b64_json" in img_data:
            image_bytes = base64.b64decode(img_data["b64_json"])
            img_file = io.BytesIO(image_bytes)

            with Image.open(img_file) as image:
                img_format = image.format or "PNG"
                has_transparency = image.mode == "RGBA" and "A" in image.getbands()
                if has_transparency and img_format.upper() != "PNG":
                    img_format = "PNG"
                    converted = io.BytesIO()
                    image.save(converted, format="PNG")
                    converted.seek(0)
                    img_file = converted
                img_file.seek(0)

            filename = self._generate_filename(prompt, img_format.lower(), idx)
        else:
            raise HTTPException(
                status_code=400,
                detail="Generated image is missing both b64_json and url",
            )

        img_file.seek(0)
        return img_file, filename, has_transparency

    @staticmethod
    def _build_base_metadata(request: ImageSaveRequest) -> Dict[str, object]:
        metadata: Dict[str, object] = {}
        if request.prompt:
            metadata["prompt"] = request.prompt
        if request.model:
            metadata["model"] = request.model
        if request.background:
            metadata["background"] = request.background
        if request.size:
            metadata["size"] = request.size
        if request.generation_response.token_usage is not None:
            metadata["token_usage"] = request.generation_response.token_usage.model_dump(
                mode="json"
            )
        if request.metadata:
            for key, value in request.metadata.items():
                if value is not None:
                    metadata[str(key)] = value
        return metadata

    async def _create_or_update_metadata(
        self,
        cosmos_service: CosmosDBService,
        upload_result: Dict[str, object],
        request: ImageSaveRequest,
        has_transparency: Optional[bool],
        image_metadata: Dict[str, str],
        deployment_name: Optional[str] = None,
        model_used: Optional[str] = None,
    ) -> None:
        asset_id = str(upload_result["blob_name"]).split(".")[0].split("/")[-1]
        width_val = upload_result.get("width")
        height_val = upload_result.get("height")
        width = int(width_val) if width_val else None
        height = int(height_val) if height_val else None

        cosmos_metadata: Dict[str, object] = {
            "id": asset_id,
            "media_type": "image",
            "blob_name": upload_result["blob_name"],
            "container": upload_result["container"],
            "url": upload_result["url"],
            "filename": upload_result["original_filename"],
            "size": upload_result.get("size"),
            "content_type": upload_result.get("content_type"),
            "folder_path": upload_result.get("folder_path"),
            "prompt": request.prompt,
            "model": model_used or request.model,
        }

        image_job_id = (
            request.metadata.get("image_job_id") if request.metadata else None
        )
        if image_job_id:
            cosmos_metadata["generation_id"] = str(image_job_id)

        if deployment_name:
            cosmos_metadata["deployment_name"] = deployment_name

        quality = getattr(request, "quality", None)
        if quality and quality != "auto":
            cosmos_metadata["quality"] = quality

        background = getattr(request, "background", None)
        if background and background != "auto":
            cosmos_metadata["background"] = background

        output_format = getattr(request, "output_format", None)
        if output_format:
            cosmos_metadata["output_format"] = output_format

        if has_transparency is not None:
            cosmos_metadata["has_transparency"] = has_transparency

        if width is not None:
            cosmos_metadata["width"] = width
        if height is not None:
            cosmos_metadata["height"] = height

        custom_meta = {
            key: value for key, value in image_metadata.items() if value is not None
        }
        if custom_meta:
            cosmos_metadata["custom_metadata"] = custom_meta

        cosmos_metadata = {
            key: value for key, value in cosmos_metadata.items() if value is not None
        }

        await self._call_service_method(
            cosmos_service,
            "upsert_asset_metadata",
            cosmos_metadata,
        )
        logger.info("Upserted Cosmos DB metadata for image: %s", asset_id)

    async def _run_analysis_on_saved_images(
        self,
        saved_images: List[Dict[str, object]],
        cosmos_service: CosmosDBService,
        request: ImageSaveRequest,
        azure_storage_service: AzureBlobStorageService,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> List[Dict[str, object]]:
        logger.info(
            "Starting analysis for %s saved images", len(saved_images)
        )
        analyzer = await self._get_analyzer()
        semaphore = asyncio.Semaphore(self._max_concurrent_io)
        completed_analyses = 0
        await self._emit_progress(
            progress_callback,
            "analyzing",
            {"status": "started", "completed": 0, "total": len(saved_images)},
        )

        async def analyze_one(
            idx: int, saved_image: Dict[str, object]
        ) -> Tuple[int, Dict[str, object]]:
            nonlocal completed_analyses
            async with semaphore:
                try:
                    blob_name = str(saved_image["blob_name"])
                    container_name = str(saved_image["container"])
                    image_content, _ = await azure_storage_service.download_asset_async(
                        blob_name,
                        container_name,
                    )
                    image_base64 = base64.b64encode(image_content).decode("utf-8")
                    custom_prompt = None
                    if request.metadata and request.metadata.get("analysis_prompt"):
                        custom_prompt = str(request.metadata["analysis_prompt"])

                    analysis = await analyzer.async_image_chat(
                        image_base64,
                        custom_prompt or analyze_image_system_message,
                    )

                    asset_id = blob_name.split(".")[0].split("/")[-1]
                    analysis_data = {
                        "summary": analysis.get(
                            "description", "No summary provided"
                        ),
                        "products": analysis.get("products", "None identified"),
                        "tags": analysis.get("tags", []),
                        "feedback": analysis.get(
                            "feedback", "No feedback provided"
                        ),
                        "analyzed_at": datetime.utcnow().isoformat(),
                    }

                    await self._call_service_method(
                        cosmos_service,
                        "update_asset_metadata",
                        asset_id,
                        "image",
                        {
                            "analysis": analysis_data,
                            "has_analysis": True,
                        },
                    )

                    result: Dict[str, object] = {
                        "blob_name": blob_name,
                        "asset_id": asset_id,
                        "analysis": analysis,
                        "success": True,
                    }
                except Exception as exc:
                    logger.error(
                        "Failed to analyze image %s: %s",
                        saved_image.get("blob_name"),
                        exc,
                    )
                    result = {
                        "blob_name": saved_image.get("blob_name"),
                        "error": str(exc),
                        "success": False,
                    }

                completed_analyses += 1
                output_index = saved_image.get("original_index", idx + 1)
                await self._emit_progress(
                    progress_callback,
                    "analyzing",
                    {
                        "status": "in_progress",
                        "completed": completed_analyses,
                        "total": len(saved_images),
                        "image_index": output_index,
                        "success": bool(result["success"]),
                    },
                )
                return idx, result

        indexed_results = await asyncio.gather(
            *(
                analyze_one(idx, saved_image)
                for idx, saved_image in enumerate(saved_images)
            )
        )

        analysis_results = [
            result for _, result in sorted(indexed_results, key=lambda item: item[0])
        ]
        await self._emit_progress(
            progress_callback,
            "analyzing",
            {
                "status": "completed",
                "completed": len(analysis_results),
                "total": len(saved_images),
                "failed": sum(
                    1 for result in analysis_results if not result.get("success")
                ),
            },
        )
        return analysis_results

    def _generate_filename(
        self,
        prompt: Optional[str],
        extension: str,
        idx: int,
    ) -> str:
        base_prompt = (prompt or "generated_image").strip()
        safe_prompt = re.sub(r"[^a-zA-Z0-9_\-]", "_", base_prompt)
        safe_prompt = re.sub(r"_+", "_", safe_prompt).strip("_.")
        if not safe_prompt:
            safe_prompt = "generated_image"
        safe_prompt = safe_prompt[:50]
        unique_suffix = uuid.uuid4().hex[:8]
        filename = f"{safe_prompt}_{idx + 1}_{unique_suffix}.{extension}"
        return self._normalize_filename(filename)

    def _generate_job_filename(
        self, image_job_id: str, extension: str, idx: int
    ) -> str:
        safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "_", image_job_id).strip("_")
        if not safe_job_id:
            raise HTTPException(status_code=400, detail="Invalid image_job_id metadata")
        safe_job_id = safe_job_id[:160]
        return self._normalize_filename(
            f"image_job_{safe_job_id}_{idx + 1}.{extension}"
        )

    @staticmethod
    async def _call_service_method(
        service: object,
        method_name: str,
        *args: object,
    ) -> object:
        method = getattr(service, method_name)
        if inspect.iscoroutinefunction(method):
            return await method(*args)
        return await asyncio.to_thread(method, *args)

    @staticmethod
    async def _emit_progress(
        callback: Optional[ProgressCallback],
        stage: str,
        details: Dict[str, object],
    ) -> None:
        if callback is not None:
            await callback(stage, details)

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        stem, dot, suffix = filename.rpartition(".")
        if not dot:
            stem = filename
            suffix = ""
        stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", stem)
        stem = re.sub(r"_+", "_", stem).strip("_.")
        if not stem:
            stem = "generated_image"
        normalized = f"{stem}.{suffix}" if suffix else stem
        if len(normalized) > 200:
            if suffix:
                normalized = f"{stem[:200 - len(suffix) - 1]}.{suffix}"
            else:
                normalized = stem[:200]
        return normalized

    async def _get_analyzer(self) -> ImageAnalyzer:
        if not self._image_analyzer:
            clients = await asyncio.to_thread(get_core_clients)
            self._image_analyzer = ImageAnalyzer(
                clients.llm_client,
                settings.LLM_DEPLOYMENT,
                async_openai_client=clients.async_llm_client,
            )
        return self._image_analyzer

    @staticmethod
    def _merge_pipeline_metadata(request: ImagePipelineRequest) -> Dict[str, object]:
        metadata: Dict[str, object] = request.metadata.copy(
        ) if request.metadata else {}
        if request.save_options.metadata:
            metadata.update(request.save_options.metadata)
        if request.analysis_options.custom_prompt:
            metadata["analysis_prompt"] = request.analysis_options.custom_prompt
        return metadata

    async def _resolve_edit_images(
        self,
        request: ImagePipelineRequest,
        *,
        azure_storage_service: Optional[AzureBlobStorageService],
    ) -> List[str]:
        images: List[str] = []
        if request.source_image_urls:
            images.extend([str(url) for url in request.source_image_urls])
        if request.source_image_base64:
            images.extend(request.source_image_base64)
        if request.source_image_blobs:
            if azure_storage_service is None:
                raise HTTPException(
                    status_code=503,
                    detail="Blob storage is required to resolve durable source images",
                )
            for reference in request.source_image_blobs:
                try:
                    content, detected_content_type = (
                        await azure_storage_service.download_asset_async(
                            reference.blob_name,
                            reference.container,
                        )
                    )
                except ResourceNotFoundError as exc:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Source image was not found: {reference.blob_name}",
                    ) from exc
                content_type = (
                    reference.content_type
                    or detected_content_type
                    or "image/png"
                )
                encoded = base64.b64encode(content).decode("ascii")
                images.append(f"data:{content_type};base64,{encoded}")
        if not images:
            raise HTTPException(
                status_code=400,
                detail="No source images provided for edit action",
            )
        return images
