import asyncio
import base64
import io
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from fastapi import HTTPException, UploadFile
from PIL import Image

from backend.core import dalle_client, llm_client, image_sas_token
from backend.core.analyze import ImageAnalyzer
from backend.core.azure_storage import AzureBlobStorageService
from backend.core.config import settings
from backend.core.cosmos_client import CosmosDBService
from backend.core.instructions import analyze_image_system_message
from backend.models.gallery import MediaType
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
)

logger = logging.getLogger(__name__)


class ImagePipelineService:
    """Service that centralises the image generation/edit/save pipeline logic."""

    def __init__(self) -> None:
        self._image_analyzer: Optional[ImageAnalyzer] = None

    # ------------------------------------------------------------------
    # Generation / Edit helpers
    # ------------------------------------------------------------------
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """Generate images via the configured DALL-E/GPT-image client."""
        try:
            # Import here to avoid circular dependencies
            from backend.core.gpt_image import GPTImageClient
            
            # Create a model-specific client
            client = GPTImageClient(
                provider=settings.MODEL_PROVIDER,
                model=request.model
            )
            
            params: Dict[str, object] = {
                "prompt": request.prompt,
                "model": request.model,
                "n": request.n,
                "size": request.size,
            }

            # Add model-specific parameters (supported by all gpt-image models)
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

            # Run sync SDK call in thread pool to not block event loop
            response = await asyncio.to_thread(client.generate_image, **params)
            token_usage = self._extract_token_usage(response)
            
            # Extract deployment metadata for tracking
            deployment_name = response.get("_deployment_name")
            model_used = response.get("_model", request.model)

            return ImageGenerationResponse(
                success=True,
                message="Refer to the imgen_model_response for details",
                imgen_model_response=response,
                token_usage=token_usage,
            )
        except Exception as exc:  # pragma: no cover - delegated to HTTP response
            logger.error("Error generating image: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    async def edit(self, request: ImageEditRequest) -> ImageGenerationResponse:
        """Edit images via the configured client using JSON payload data."""
        try:
            # Validate mini model restrictions
            if request.model == "gpt-image-1-mini":
                raise HTTPException(
                    status_code=400,
                    detail="gpt-image-1-mini does not support image editing. Please use gpt-image-1 or gpt-image-1.5 for image editing operations."
                )
            
            # Import here to avoid circular dependencies
            from backend.core.gpt_image import GPTImageClient
            
            # Create a model-specific client
            client = GPTImageClient(
                provider=settings.MODEL_PROVIDER,
                model=request.model
            )
            
            params: Dict[str, object] = {
                "prompt": request.prompt,
                "model": request.model,
                "n": request.n,
                "size": request.size,
                "image": request.image,
            }

            if request.mask:
                params["mask"] = request.mask

            # Add model-specific parameters
            if request.quality:
                params["quality"] = request.quality
            if request.output_format != "png":
                params["output_format"] = request.output_format
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

            # Run sync SDK call in thread pool to not block event loop
            response = await asyncio.to_thread(client.edit_image, **params)
            token_usage = self._extract_token_usage(response)
            
            # Extract deployment metadata for tracking
            deployment_name = response.get("_deployment_name")
            model_used = response.get("_model", request.model)

            return ImageGenerationResponse(
                success=True,
                message="Refer to the imgen_model_response for details",
                imgen_model_response=response,
                token_usage=token_usage,
            )
        except Exception as exc:  # pragma: no cover - delegated to HTTP response
            logger.error("Error editing image: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    async def edit_with_uploads(
        self,
        *,
        prompt: str,
        model: str,
        n: int,
        size: str,
        quality: str,
        output_format: str,
        input_fidelity: str,
        images: List[UploadFile],
        mask: Optional[UploadFile] = None,
    ) -> ImageGenerationResponse:
        """Edit images using uploaded multipart files."""

        # Validate mini model restrictions
        if model == "gpt-image-1-mini":
            raise HTTPException(
                status_code=400,
                detail="gpt-image-1-mini does not support image editing. Please use gpt-image-1 or gpt-image-1.5 for image editing operations."
            )

        if input_fidelity not in ["low", "high"]:
            raise HTTPException(
                status_code=400,
                detail="input_fidelity must be either 'low' or 'high'",
            )

        max_file_size_mb = settings.GPT_IMAGE_MAX_FILE_SIZE_MB
        temp_files: List[Tuple[int, str]] = []

        try:
            image_file_paths: List[str] = []
            for idx, upload in enumerate(images):
                contents = await upload.read()
                file_size_mb = len(contents) / (1024 * 1024)
                if file_size_mb > max_file_size_mb:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Image {idx + 1} exceeds maximum size of {max_file_size_mb}MB"
                        ),
                    )

                ext = self._determine_extension(upload.content_type, contents)
                temp_fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
                temp_files.append((temp_fd, temp_path))

                with os.fdopen(temp_fd, "wb") as file_obj:
                    file_obj.write(contents)

                image_file_paths.append(temp_path)
                logger.info(
                    "Saved image %s to %s with format %s", idx + 1, temp_path, ext
                )

            mask_path: Optional[str] = None
            if mask:
                mask_contents = await mask.read()
                mask_ext = self._determine_extension(
                    mask.content_type, mask_contents)
                mask_fd, mask_path = tempfile.mkstemp(suffix=f".{mask_ext}")
                temp_files.append((mask_fd, mask_path))
                with os.fdopen(mask_fd, "wb") as mask_file:
                    mask_file.write(mask_contents)
                logger.info("Saved mask to %s with format %s",
                            mask_path, mask_ext)

            params: Dict[str, object] = {
                "prompt": prompt,
                "model": model,
                "n": n,
                "size": size,
            }

            # Add quality and input_fidelity for all gpt-image models
            params["quality"] = quality
            if input_fidelity != "low":
                params["input_fidelity"] = input_fidelity

            response = await self._invoke_edit_with_files(
                image_file_paths, mask_path, params, model
            )
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
            raise HTTPException(status_code=500, detail=str(exc))
        finally:
            self._cleanup_temp_files(temp_files)

    async def save(
        self,
        request: ImageSaveRequest,
        *,
        azure_storage_service: AzureBlobStorageService,
        cosmos_service: Optional[CosmosDBService] = None,
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
        saved_images: List[Dict[str, object]] = []
        
        # Extract deployment metadata for tracking
        deployment_name = request.generation_response.imgen_model_response.get("_deployment_name")
        model_used = request.generation_response.imgen_model_response.get("_model")

        for idx, img_data in enumerate(images_data):
            # Run sync file preparation in thread pool to avoid blocking
            img_file, filename, has_transparency = await asyncio.to_thread(
                self._prepare_image_file, img_data, request.prompt, idx
            )
            image_metadata = combined_metadata.copy()
            image_metadata["image_index"] = str(idx + 1)
            image_metadata["total_images"] = str(len(images_data))

            upload = UploadFile(filename=filename, file=img_file)
            result = await azure_storage_service.upload_asset(
                upload,
                MediaType.IMAGE.value,
                metadata=None,
                folder_path=request.folder_path,
            )

            if cosmos_service:
                # Run sync cosmos DB call in thread pool to avoid blocking
                await asyncio.to_thread(
                    self._create_or_update_metadata,
                    cosmos_service,
                    result,
                    request,
                    has_transparency,
                    image_metadata,
                    deployment_name,
                    model_used,
                )

            saved_images.append(result)
            await upload.close()

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
            if action_step == "edit":
                if source_images:
                    generation_response = await self.edit_with_uploads(
                        prompt=pipeline_request.prompt,
                        model=pipeline_request.model,
                        n=pipeline_request.n,
                        size=pipeline_request.size,
                        quality=pipeline_request.quality or "auto",
                        output_format=pipeline_request.output_format or "png",
                        input_fidelity=pipeline_request.input_fidelity or "low",
                        images=source_images,
                        mask=mask,
                    )
                else:
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
                        image=self._resolve_edit_images(pipeline_request),
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
        except HTTPException as exc:
            steps.append(
                PipelineStepResult(
                    step=action_step,
                    success=False,
                    message=str(exc.detail),
                )
            )
            raise
        except Exception as exc:  # pragma: no cover - delegated to HTTP response
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
                )
                steps.append(
                    PipelineStepResult(
                        step="save",
                        success=True,
                        message=f"Saved {save_response.total_saved} image(s)",
                    )
                )
            except HTTPException as exc:
                steps.append(
                    PipelineStepResult(
                        step="save",
                        success=False,
                        message=str(exc.detail),
                    )
                )
                raise

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

    async def _invoke_edit_with_files(
        self,
        image_paths: List[str],
        mask_path: Optional[str],
        params: Dict[str, object],
        model: str,
    ) -> Dict[str, object]:
        # Import here to avoid circular dependencies
        from backend.core.gpt_image import GPTImageClient
        
        # Create a model-specific client
        client = GPTImageClient(
            provider=settings.MODEL_PROVIDER,
            model=model
        )
        
        # Run sync SDK call in thread pool to not block event loop
        # We use a helper function that handles file opening/closing in the thread
        def _sync_edit_with_files():
            if len(image_paths) == 1:
                with open(image_paths[0], "rb") as image_file:
                    params["image"] = image_file
                    if mask_path:
                        with open(mask_path, "rb") as mask_file:
                            params["mask"] = mask_file
                            return client.edit_image(**params)
                    return client.edit_image(**params)

            open_files: List[io.BufferedReader] = []
            try:
                image_files = []
                for path in image_paths:
                    file_obj = open(path, "rb")
                    open_files.append(file_obj)
                    image_files.append(file_obj)
                params["image"] = image_files

                if mask_path:
                    mask_file = open(mask_path, "rb")
                    open_files.append(mask_file)
                    params["mask"] = mask_file

                return client.edit_image(**params)
            finally:
                for file_obj in open_files:
                    file_obj.close()

        return await asyncio.to_thread(_sync_edit_with_files)

    @staticmethod
    def _cleanup_temp_files(temp_files: List[Tuple[int, str]]) -> None:
        for _, path in temp_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as exc:
                logger.warning("Failed to remove temp file %s: %s", path, exc)

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
        elif "url" in img_data:
            response = requests.get(img_data["url"])
            if response.status_code != 200:
                logger.error(
                    "Failed to download image from URL: %s", response.status_code
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to download image from URL",
                )
            img_file = io.BytesIO(response.content)
            filename = self._generate_filename(prompt, "png", idx)

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
        if request.metadata:
            for key, value in request.metadata.items():
                if value is not None:
                    metadata[str(key)] = value
        return metadata

    def _create_or_update_metadata(
        self,
        cosmos_service: CosmosDBService,
        upload_result: Dict[str, object],
        request: ImageSaveRequest,
        has_transparency: Optional[bool],
        image_metadata: Dict[str, str],
        deployment_name: Optional[str] = None,
        model_used: Optional[str] = None,
    ) -> None:
        try:
            asset_id = str(upload_result["blob_name"]).split(".")[
                0].split("/")[-1]
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
            
            # Add deployment name for cost attribution
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
                key: value
                for key, value in image_metadata.items()
                if value is not None
            }
            if custom_meta:
                cosmos_metadata["custom_metadata"] = custom_meta

            cosmos_metadata = {
                key: value for key, value in cosmos_metadata.items() if value is not None
            }

            cosmos_service.create_asset_metadata(cosmos_metadata)
            logger.info(
                "Created Cosmos DB metadata for image: %s", asset_id
            )
        except Exception as exc:
            logger.warning("Failed to create Cosmos DB metadata: %s", exc)

    async def _run_analysis_on_saved_images(
        self,
        saved_images: List[Dict[str, object]],
        cosmos_service: CosmosDBService,
        request: ImageSaveRequest,
    ) -> List[Dict[str, object]]:
        logger.info(
            "Starting analysis for %s saved images", len(saved_images)
        )
        analyzer = self._get_analyzer()
        analysis_results: List[Dict[str, object]] = []

        for saved_image in saved_images:
            try:
                image_url = str(saved_image["url"])
                blob_name = str(saved_image["blob_name"])
                if "?" not in image_url:
                    image_url = f"{image_url}?{image_sas_token}"

                # Run sync HTTP request in thread pool
                response = await asyncio.to_thread(
                    requests.get, image_url, timeout=30
                )
                if response.status_code != 200:
                    raise Exception(
                        f"Failed to download image: HTTP {response.status_code}"
                    )

                image_base64 = base64.b64encode(
                    response.content).decode("utf-8")
                custom_prompt = None
                if request.metadata and request.metadata.get("analysis_prompt"):
                    custom_prompt = str(request.metadata["analysis_prompt"])

                # Run sync LLM call in thread pool
                analysis = await asyncio.to_thread(
                    analyzer.image_chat,
                    image_base64,
                    custom_prompt or analyze_image_system_message,
                )

                asset_id = blob_name.split(".")[0].split("/")[-1]
                analysis_data = {
                    "summary": analysis.get("description", "No summary provided"),
                    "products": analysis.get("products", "None identified"),
                    "tags": analysis.get("tags", []),
                    "feedback": analysis.get("feedback", "No feedback provided"),
                    "analyzed_at": datetime.utcnow().isoformat(),
                }

                # Run sync cosmos DB call in thread pool to avoid blocking
                await asyncio.to_thread(
                    cosmos_service.update_asset_metadata,
                    asset_id,
                    "image",
                    {
                        "analysis": analysis_data,
                        "has_analysis": True,
                    },
                )

                analysis_results.append(
                    {
                        "blob_name": blob_name,
                        "asset_id": asset_id,
                        "analysis": analysis,
                        "success": True,
                    }
                )
            except Exception as exc:
                logger.error(
                    "Failed to analyze image %s: %s", saved_image.get(
                        "blob_name"), exc
                )
                analysis_results.append(
                    {
                        "blob_name": saved_image.get("blob_name"),
                        "error": str(exc),
                        "success": False,
                    }
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

    def _get_analyzer(self) -> ImageAnalyzer:
        if not self._image_analyzer:
            self._image_analyzer = ImageAnalyzer(
                llm_client, settings.LLM_DEPLOYMENT)
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

    @staticmethod
    def _resolve_edit_images(request: ImagePipelineRequest) -> List[str]:
        images: List[str] = []
        if request.source_image_urls:
            images.extend([str(url) for url in request.source_image_urls])
        if request.source_image_base64:
            images.extend(request.source_image_base64)
        if not images:
            raise HTTPException(
                status_code=400,
                detail="No source images provided for edit action",
            )
        return images
