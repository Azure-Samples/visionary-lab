from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import Dict, List, Optional
from datetime import datetime
import re
import logging
import base64
import requests
import json
import io
from PIL import Image
import uuid
from pathlib import Path
from pydantic import ValidationError

from backend.models.images import (
    ImageGenerationRequest,
    ImageEditRequest,
    ImageGenerationResponse,
    ImageListRequest,
    ImageListResponse,
    ImageDeleteRequest,
    ImageDeleteResponse,
    ImageAnalyzeRequest,
    ImageAnalyzeCustomRequest,
    ImageAnalyzeCustomRequest,
    ImageAnalyzeResponse,
    ImagePromptEnhancementRequest,
    ImagePromptEnhancementResponse,
    ImagePromptBrandProtectionRequest,
    ImagePromptBrandProtectionResponse,
    ImageFilenameGenerateRequest,
    ImageFilenameGenerateResponse,
    ImageSaveRequest,
    ImageSaveResponse,
    ImageGenerateWithAnalysisRequest,
    ImagePipelineRequest,
    ImagePipelineResponse,
    PipelineAction,
    PipelineSaveOptions,
    PipelineAnalysisOptions,
)
from backend.core import llm_client, image_sas_token
from backend.core.azure_storage import AzureBlobStorageService
from backend.core.analyze import ImageAnalyzer
from backend.core.config import settings
from backend.core.instructions import (
    analyze_image_system_message,
    img_prompt_enhance_msg,
    brand_protect_neutralize_msg,
    brand_protect_replace_msg,
    filename_system_message,
)
from backend.core.cosmos_client import CosmosDBService
from backend.core.image_pipeline import ImagePipelineService

router = APIRouter()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pipeline_service = ImagePipelineService()


def get_cosmos_service() -> Optional[CosmosDBService]:
    """Dependency to get Cosmos DB service instance (optional)"""
    try:
        # Check if we have either managed identity or key-based auth configured
        if settings.AZURE_COSMOS_DB_ENDPOINT and (settings.USE_MANAGED_IDENTITY or settings.AZURE_COSMOS_DB_KEY):
            return CosmosDBService()
        return None
    except Exception as e:
        logger.warning(f"Cosmos DB service unavailable: {e}")
        return None


def normalize_filename(filename: str) -> str:
    """
    Normalize a filename to be safe for file systems.

    Args:
        filename: The filename to normalize

    Returns:
        A normalized filename safe for most file systems
    """
    if not filename:
        return filename

    # Use pathlib to handle the filename safely
    path = Path(filename)

    # Get the stem (filename without extension) and suffix (extension)
    stem = path.stem
    suffix = path.suffix

    # Remove or replace invalid characters for most filesystems
    # Keep alphanumeric, hyphens, underscores, and dots
    stem = re.sub(r"[^a-zA-Z0-9_\-.]", "_", stem)

    # Remove multiple consecutive underscores
    stem = re.sub(r"_+", "_", stem)

    # Remove leading/trailing underscores and dots
    stem = stem.strip("_.")

    # Ensure the filename isn't empty
    if not stem:
        stem = "generated_image"

    # Reconstruct the filename
    normalized = f"{stem}{suffix}" if suffix else stem

    # Ensure the filename isn't too long (most filesystems support 255 chars)
    if len(normalized) > 200:  # Leave some room for additional suffixes
        # Truncate the stem but keep the extension
        max_stem_length = 200 - len(suffix)
        stem = stem[:max_stem_length]
        normalized = f"{stem}{suffix}" if suffix else stem

    return normalized


async def generate_filename_for_prompt(prompt: str, extension: str = None) -> str:
    """
    Generate a filename using the existing filename generation endpoint.

    Args:
        prompt: The prompt used for image generation
        extension: File extension (e.g., '.png', '.jpg')

    Returns:
        Generated filename or None if generation fails
    """
    try:
        # Create request for filename generation
        filename_request = ImageFilenameGenerateRequest(
            prompt=prompt, extension=extension
        )

        # Call the filename generation function directly
        filename_response = generate_image_filename(filename_request)

        # Normalize the generated filename
        generated_filename = normalize_filename(filename_response.filename)

        return generated_filename

    except Exception as e:
        return None


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest):
    """Generate an image based on the provided prompt and settings"""
    return await pipeline_service.generate(request)


@router.post("/edit", response_model=ImageGenerationResponse)
async def edit_image(request: ImageEditRequest):
    """Edit an input image based on the provided prompt, mask image and settings"""
    return await pipeline_service.edit(request)


@router.post("/edit/upload", response_model=ImageGenerationResponse)
async def edit_image_upload(
    prompt: str = Form(...),
    model: str = Form("gpt-image-1"),
    n: int = Form(1),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    output_format: str = Form("png"),
    input_fidelity: str = Form("low"),
    image: List[UploadFile] = File(...),
    mask: Optional[UploadFile] = File(None),
):
    """Edit input images uploaded via multipart form data."""
    return await pipeline_service.edit_with_uploads(
        prompt=prompt,
        model=model,
        n=n,
        size=size,
        quality=quality,
        output_format=output_format,
        input_fidelity=input_fidelity,
        images=image,
        mask=mask,
    )


@router.post("/save", response_model=ImageSaveResponse)
async def save_generated_images(
    request: ImageSaveRequest,
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()
    ),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """Save generated images to blob storage and update metadata."""
    return await pipeline_service.save(
        request,
        azure_storage_service=azure_storage_service,
        cosmos_service=cosmos_service,
    )


@router.post("/pipeline", response_model=ImagePipelineResponse)
async def process_image_pipeline(
    payload: str = Form(...),
    source_images: Optional[List[UploadFile]] = File(
        None, description="Source images for edit workflows"
    ),
    image: Optional[List[UploadFile]] = File(
        None,
        description="Legacy field name for source images",
    ),
    mask: Optional[UploadFile] = File(None),
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()
    ),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """Unified pipeline endpoint for generation, editing, saving, and analysis."""
    try:
        pipeline_request = ImagePipelineRequest.parse_raw(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json()))

    storage_service = (
        azure_storage_service if pipeline_request.save_options.enabled else None
    )

    uploaded_images: Optional[List[UploadFile]] = None
    if source_images or image:
        uploaded_images = []
        if source_images:
            uploaded_images.extend(source_images)
        if image:
            uploaded_images.extend(image)

    return await pipeline_service.process_pipeline(
        pipeline_request,
        azure_storage_service=storage_service,
        cosmos_service=cosmos_service,
        source_images=uploaded_images,
        mask=mask,
    )


@router.post("/generate-with-analysis", response_model=ImageSaveResponse)
async def generate_image_with_analysis(
    req: ImageGenerateWithAnalysisRequest,
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService()
    ),
    cosmos_service: Optional[CosmosDBService] = Depends(get_cosmos_service),
):
    """Generate, save, and optionally analyze images in one call."""
    pipeline_request = ImagePipelineRequest(
        action=PipelineAction.GENERATE,
        prompt=req.prompt,
        model=req.model,
        n=req.n,
        size=req.size,
        response_format=req.response_format,
        quality=req.quality,
        output_format=req.output_format,
        output_compression=req.output_compression,
        background=req.background,
        moderation=req.moderation,
        user=req.user,
        save_options=PipelineSaveOptions(
            enabled=True,
            save_all=req.save_all,
            folder_path=req.folder_path,
        ),
        analysis_options=PipelineAnalysisOptions(
            enabled=req.analyze,
        ),
    )

    pipeline_response = await pipeline_service.process_pipeline(
        pipeline_request,
        azure_storage_service=azure_storage_service,
        cosmos_service=cosmos_service,
    )

    if not pipeline_response.save:
        raise HTTPException(
            status_code=500,
            detail="Pipeline did not produce a save response",
        )

    return pipeline_response.save

@router.post("/list", response_model=ImageListResponse)
async def list_images(request: ImageListRequest):
    """List generated images with pagination"""
    try:
        # TODO: Implement image listing:
        # - Get images from storage
        # - Apply pagination
        # - Add image URLs and metadata

        return ImageListResponse(
            success=True, images=[], total=0, limit=request.limit, offset=request.offset
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete", response_model=ImageDeleteResponse)
async def delete_image(request: ImageDeleteRequest):
    """Delete a generated image"""
    try:
        # TODO: Implement image deletion:
        # - Validate image exists
        # - Remove from storage
        # - Clean up any related resources

        return ImageDeleteResponse(
            success=True,
            message=f"Image deletion endpoint (skeleton)",
            image_id=request.image_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=ImageAnalyzeResponse)
def analyze_image(req: ImageAnalyzeRequest):
    """
    Analyze an image using an LLM.

    Args:
        image_path: path on Azure Blob Storage. Supports a full URL with or without a SAS token.
        OR
        base64_image: Base64-encoded image data to analyze directly.

    Returns:
        Response containing description, products, tags, and feedback generated by the LLM.
    """
    try:
        # Initialize image_content
        image_content = None

        # Option 1: Process from URL/path
        if req.image_path:
            file_path = req.image_path

            # check if the path is a valid Azure blob storage path
            pattern = r"^https://[a-z0-9]+\.blob\.core\.windows\.net/[a-z0-9]+/.+"
            match = re.match(pattern, file_path)

            if not match:
                raise ValueError("Invalid Azure blob storage path")
            else:
                # check if the path contains a SAS token
                if "?" not in file_path:
                    file_path += f"?{image_sas_token}"

            # Download the image from the URL
            response = requests.get(file_path, timeout=30)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to download image: HTTP {response.status_code}",
                )

            # Get image content from response
            image_content = response.content

        # Option 2: Process from base64 string
        elif req.base64_image:
            try:
                # Decode base64 to binary
                image_content = base64.b64decode(req.base64_image)
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid base64 image data: {str(e)}"
                )

        # Process the image with PIL to handle transparency properly
        try:
            # Open the image with PIL
            with Image.open(io.BytesIO(image_content)) as img:
                # Check if it's a transparent PNG
                has_transparency = img.mode == "RGBA" and "A" in img.getbands()

                if has_transparency:
                    # Create a white background
                    background = Image.new(
                        "RGBA", img.size, (255, 255, 255, 255))
                    # Paste the image on the background
                    background.paste(img, (0, 0), img)
                    # Convert to RGB (remove alpha channel)
                    background = background.convert("RGB")

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    background.save(img_byte_arr, format="JPEG")
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()

                # Also try to resize if the image is very large (LLM models have token limits)
                # This is optional but can help with very large images
                width, height = img.size
                if width > 1500 or height > 1500:
                    # Calculate new dimensions
                    max_dimension = 1500
                    if width > height:
                        new_width = max_dimension
                        new_height = int(height * (max_dimension / width))
                    else:
                        new_height = max_dimension
                        new_width = int(width * (max_dimension / height))

                    # Resize the image
                    if has_transparency:
                        # We already have the background image from above
                        resized_img = background.resize(
                            (new_width, new_height))
                    else:
                        resized_img = img.resize((new_width, new_height))

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    resized_img.save(
                        img_byte_arr,
                        format="JPEG" if resized_img.mode == "RGB" else "PNG",
                    )
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()
        except Exception as img_error:
            logger.error(f"Error processing image with PIL: {str(img_error)}")
            # If PIL processing fails, continue with the original image

        # Convert to base64
        image_base64 = base64.b64encode(image_content).decode("utf-8")
        # Remove data URL prefix if present
        image_base64 = re.sub(r"^data:image/.+;base64,", "", image_base64)

        # analyze the image using the LLM
        image_analyzer = ImageAnalyzer(llm_client, settings.LLM_DEPLOYMENT)
        insights = image_analyzer.image_chat(
            image_base64, analyze_image_system_message)

        description = insights.get("description")
        products = insights.get("products")
        tags = insights.get("tags")
        feedback = insights.get("feedback")

        return ImageAnalyzeResponse(
            description=description, products=products, tags=tags, feedback=feedback
        )

    except Exception as e:
        logger.error(f"Error analyzing image: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error analyzing image: {str(e)}")


@router.post("/analyze-custom", response_model=ImageAnalyzeResponse)
def analyze_image_custom(req: ImageAnalyzeCustomRequest):
    """
    Analyze an image using a custom prompt while maintaining the same response structure.
    
    Args:
        image_path: path on Azure Blob Storage. Supports a full URL with or without a SAS token.
        OR
        base64_image: Base64-encoded image data to analyze directly.
        custom_prompt: Custom instructions for the analysis.
        
    Returns:
        Response containing description, products, tags, and feedback based on custom prompt.
    """
    try:
        # Initialize image_content
        image_content = None

        # Option 1: Process from URL/path  
        if req.image_path:
            file_path = req.image_path

            # check if the path is a valid Azure blob storage path
            pattern = r"^https://[a-z0-9]+\.blob\.core\.windows\.net/[a-z0-9]+/.+"
            match = re.match(pattern, file_path)

            if not match:
                raise ValueError("Invalid Azure blob storage path")
            else:
                # check if the path contains a SAS token
                if "?" not in file_path:
                    file_path += f"?{image_sas_token}"

            # Download the image from the URL
            response = requests.get(file_path, timeout=30)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to download image: HTTP {response.status_code}",
                )

            # Get image content from response
            image_content = response.content

        # Option 2: Process from base64 string
        elif req.base64_image:
            try:
                # Decode base64 to binary
                image_content = base64.b64decode(req.base64_image)
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid base64 image data: {str(e)}"
                )

        # Process the image with PIL to handle transparency properly (same as regular analyze)
        try:
            # Open the image with PIL
            with Image.open(io.BytesIO(image_content)) as img:
                # Check if it's a transparent PNG
                has_transparency = img.mode == "RGBA" and "A" in img.getbands()

                if has_transparency:
                    # Create a white background
                    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    # Paste the image on the background
                    background.paste(img, (0, 0), img)
                    # Convert to RGB (remove alpha channel)
                    background = background.convert("RGB")

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    background.save(img_byte_arr, format="JPEG")
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()

                # Also try to resize if the image is very large (LLM models have token limits)
                width, height = img.size
                if width > 1500 or height > 1500:
                    # Calculate new dimensions
                    max_dimension = 1500
                    if width > height:
                        new_width = max_dimension
                        new_height = int(height * (max_dimension / width))
                    else:
                        new_height = max_dimension
                        new_width = int(width * (max_dimension / height))

                    # Resize the image
                    if has_transparency:
                        # We already have the background image from above
                        resized_img = background.resize((new_width, new_height))
                    else:
                        resized_img = img.resize((new_width, new_height))

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    resized_img.save(
                        img_byte_arr,
                        format="JPEG" if resized_img.mode == "RGB" else "PNG",
                    )
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()
        except Exception as img_error:
            logger.error(f"Error processing image with PIL: {str(img_error)}")
            # If PIL processing fails, continue with the original image

        # Convert to base64
        image_base64 = base64.b64encode(image_content).decode("utf-8")
        # Remove data URL prefix if present
        image_base64 = re.sub(r"^data:image/.+;base64,", "", image_base64)

        # Create custom system message using the provided custom prompt
        custom_prompt = req.custom_prompt
        if not custom_prompt or not custom_prompt.strip():
            raise HTTPException(
                status_code=400, detail="Custom prompt is required for custom analysis"
            )

        custom_system_message = f"""You are an expert in analyzing images.
You are provided with a single image to analyze in detail.

CUSTOM ANALYSIS INSTRUCTIONS:
{custom_prompt}

Your task is to extract the following based on the custom instructions above:
1. detailed description based on the custom requirements above
2. named brands or named products visible in the image  
3. metadata tags useful for organizing and searching content. Limit to the 5 most relevant tags.
4. feedback to improve the image based on the custom criteria above

Return the result as a valid JSON object:
{{
    "description": "<Custom analysis based on provided instructions>",
    "products": "<named brands / named products identified>",
    "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
    "feedback": "<Feedback based on custom criteria>"
}}
"""

        # analyze the image using the LLM with custom prompt
        image_analyzer = ImageAnalyzer(llm_client, settings.LLM_DEPLOYMENT)
        insights = image_analyzer.image_chat(image_base64, custom_system_message)

        description = insights.get("description")
        products = insights.get("products") 
        tags = insights.get("tags")
        feedback = insights.get("feedback")

        return ImageAnalyzeResponse(
            description=description, products=products, tags=tags, feedback=feedback
        )

    except Exception as e:
        logger.error(f"Error analyzing image with custom prompt: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error analyzing image with custom prompt: {str(e)}")


@router.post("/analyze-custom", response_model=ImageAnalyzeResponse)
def analyze_image_custom(req: ImageAnalyzeCustomRequest):
    """
    Analyze an image using a custom prompt while maintaining the same response structure.
    
    Args:
        image_path: path on Azure Blob Storage. Supports a full URL with or without a SAS token.
        OR
        base64_image: Base64-encoded image data to analyze directly.
        custom_prompt: Custom instructions for the analysis.
        
    Returns:
        Response containing description, products, tags, and feedback based on custom prompt.
    """
    try:
        # Initialize image_content
        image_content = None

        # Option 1: Process from URL/path  
        if req.image_path:
            file_path = req.image_path

            # check if the path is a valid Azure blob storage path
            pattern = r"^https://[a-z0-9]+\.blob\.core\.windows\.net/[a-z0-9]+/.+"
            match = re.match(pattern, file_path)

            if not match:
                raise ValueError("Invalid Azure blob storage path")
            else:
                # check if the path contains a SAS token
                if "?" not in file_path:
                    file_path += f"?{image_sas_token}"

            # Download the image from the URL
            response = requests.get(file_path, timeout=30)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to download image: HTTP {response.status_code}",
                )

            # Get image content from response
            image_content = response.content

        # Option 2: Process from base64 string
        elif req.base64_image:
            try:
                # Decode base64 to binary
                image_content = base64.b64decode(req.base64_image)
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid base64 image data: {str(e)}"
                )

        # Process the image with PIL to handle transparency properly (same as regular analyze)
        try:
            # Open the image with PIL
            with Image.open(io.BytesIO(image_content)) as img:
                # Check if it's a transparent PNG
                has_transparency = img.mode == "RGBA" and "A" in img.getbands()

                if has_transparency:
                    # Create a white background
                    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    # Paste the image on the background
                    background.paste(img, (0, 0), img)
                    # Convert to RGB (remove alpha channel)
                    background = background.convert("RGB")

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    background.save(img_byte_arr, format="JPEG")
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()

                # Also try to resize if the image is very large (LLM models have token limits)
                width, height = img.size
                if width > 1500 or height > 1500:
                    # Calculate new dimensions
                    max_dimension = 1500
                    if width > height:
                        new_width = max_dimension
                        new_height = int(height * (max_dimension / width))
                    else:
                        new_height = max_dimension
                        new_width = int(width * (max_dimension / height))

                    # Resize the image
                    if has_transparency:
                        # We already have the background image from above
                        resized_img = background.resize((new_width, new_height))
                    else:
                        resized_img = img.resize((new_width, new_height))

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    resized_img.save(
                        img_byte_arr,
                        format="JPEG" if resized_img.mode == "RGB" else "PNG",
                    )
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()
        except Exception as img_error:
            logger.error(f"Error processing image with PIL: {str(img_error)}")
            # If PIL processing fails, continue with the original image

        # Convert to base64
        image_base64 = base64.b64encode(image_content).decode("utf-8")
        # Remove data URL prefix if present
        image_base64 = re.sub(r"^data:image/.+;base64,", "", image_base64)

        # Create custom system message using the provided custom prompt
        custom_prompt = req.custom_prompt
        if not custom_prompt or not custom_prompt.strip():
            raise HTTPException(
                status_code=400, detail="Custom prompt is required for custom analysis"
            )

        custom_system_message = f"""You are an expert in analyzing images.
You are provided with a single image to analyze in detail.

CUSTOM ANALYSIS INSTRUCTIONS:
{custom_prompt}

Your task is to extract the following based on the custom instructions above:
1. detailed description based on the custom requirements above
2. named brands or named products visible in the image  
3. metadata tags useful for organizing and searching content. Limit to the 5 most relevant tags.
4. feedback to improve the image based on the custom criteria above

Return the result as a valid JSON object:
{{
    "description": "<Custom analysis based on provided instructions>",
    "products": "<named brands / named products identified>",
    "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
    "feedback": "<Feedback based on custom criteria>"
}}
"""

        # analyze the image using the LLM with custom prompt
        image_analyzer = ImageAnalyzer(llm_client, settings.LLM_DEPLOYMENT)
        insights = image_analyzer.image_chat(image_base64, custom_system_message)

        description = insights.get("description")
        products = insights.get("products") 
        tags = insights.get("tags")
        feedback = insights.get("feedback")

        return ImageAnalyzeResponse(
            description=description, products=products, tags=tags, feedback=feedback
        )

    except Exception as e:
        logger.error(f"Error analyzing image with custom prompt: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error analyzing image with custom prompt: {str(e)}")


@router.post("/prompt/enhance", response_model=ImagePromptEnhancementResponse)
def enhance_image_prompt(req: ImagePromptEnhancementRequest):
    """
    Improves a given text to image prompt considering best practices for the image generation model.
    """
    try:
        system_message = img_prompt_enhance_msg

        # Ensure LLM client is available
        if llm_client is None:
            raise HTTPException(
                status_code=503,
                detail="LLM service is currently unavailable. Please check your environment configuration.",
            )

        original_prompt = req.original_prompt
        # Call the LLM to enhance the prompt
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": original_prompt},
        ]
        response = llm_client.chat.completions.create(
            messages=messages,
            model=settings.LLM_DEPLOYMENT,
            response_format={"type": "json_object"},
        )
        enhanced_prompt = json.loads(
            response.choices[0].message.content).get("prompt")
        return ImagePromptEnhancementResponse(enhanced_prompt=enhanced_prompt)

    except Exception as e:
        logger.error(f"Error enhancing image prompt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompt/protect", response_model=ImagePromptBrandProtectionResponse)
def protect_image_prompt(req: ImagePromptBrandProtectionRequest):
    """
    Rewrites a given prompt for brand protection.
    """
    try:
        if req.brands_to_protect:
            if req.protection_mode == "replace":
                system_message = brand_protect_replace_msg.format(
                    brands=req.brands_to_protect
                )
            elif req.protection_mode == "neutralize":
                system_message = brand_protect_neutralize_msg.format(
                    brands=req.brands_to_protect
                )
        else:
            return ImagePromptBrandProtectionResponse(
                enhanced_prompt=req.original_prompt
            )

        # Ensure LLM client is available
        if llm_client is None:
            raise HTTPException(
                status_code=503,
                detail="LLM service is currently unavailable. Please check your environment configuration.",
            )

        original_prompt = req.original_prompt
        # Call the LLM to enhance the prompt
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": original_prompt},
        ]
        response = llm_client.chat.completions.create(
            messages=messages,
            model=settings.LLM_DEPLOYMENT,
            response_format={"type": "json_object"},
        )
        enhanced_prompt = json.loads(
            response.choices[0].message.content).get("prompt")
        return ImagePromptEnhancementResponse(enhanced_prompt=enhanced_prompt)

    except Exception as e:
        logger.error(f"Error enhancing image prompt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filename/generate", response_model=ImageFilenameGenerateResponse)
def generate_image_filename(req: ImageFilenameGenerateRequest):
    """
    Creates a unique name for a file based on the text prompt used for creating the image.

    Args:
        prompt: Text prompt.
        extension: Optional file extension to append (e.g., ".png", ".jpg").

    Returns:
        filename: Generated filename Example: "xbox_promotion_party_venice_beach_yxKrKLT9StqhtxZWikdtRQ.png"
    """

    try:
        # Ensure LLM client is available
        if llm_client is None:
            raise HTTPException(
                status_code=503,
                detail="LLM service is currently unavailable. Please check your environment configuration.",
            )

        # Validate prompt
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(
                status_code=400, detail="Prompt must not be empty.")

        # Call the LLM to enhance the prompt
        messages = [
            {"role": "system", "content": filename_system_message},
            {"role": "user", "content": req.prompt},
        ]
        response = llm_client.chat.completions.create(
            messages=messages,
            model=settings.LLM_DEPLOYMENT,
            response_format={"type": "json_object"},
        )
        filename = json.loads(response.choices[0].message.content).get(
            "filename_prefix"
        )

        # Validate and sanitize filename
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=500, detail="Failed to generate a valid filename prefix."
            )
        # Remove invalid characters for most filesystems
        filename = re.sub(r"[^a-zA-Z0-9_\-]", "_", filename.strip())

        # add a sort unique identifier to the filename
        uid = uuid.uuid4()
        short_uid = base64.urlsafe_b64encode(
            uid.bytes).rstrip(b"=").decode("ascii")
        filename += f"_{short_uid}"

        if req.extension:
            ext = req.extension.lstrip(".")
            filename += f".{ext}"

        return ImageFilenameGenerateResponse(filename=filename)

    except Exception as e:
        logger.error(f"Error generating filename: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
