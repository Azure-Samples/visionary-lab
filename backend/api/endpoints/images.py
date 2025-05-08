from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from typing import Dict, List, Optional
import re
import logging
import base64
import requests
import json
import io
from PIL import Image
from tempfile import SpooledTemporaryFile
import tempfile
import os
import uuid

from models.images import (
    ImageGenerationRequest,
    ImageEditRequest,
    ImageGenerationResponse,
    ImageListRequest,
    ImageListResponse,
    ImageDeleteRequest,
    ImageDeleteResponse,
    ImageAnalyzeRequest,
    ImageAnalyzeResponse,
    ImagePromptEnhancementRequest,
    ImagePromptEnhancementResponse,
    ImagePromptBrandProtectionRequest,
    ImagePromptBrandProtectionResponse,
    ImageFilenameGenerateRequest,
    ImageFilenameGenerateResponse,
    ImageSaveRequest,
    ImageSaveResponse,
    TokenUsage,
    InputTokensDetails
)
from models.gallery import MediaType
from core import llm_client, dalle_client, image_sas_token
from core.azure_storage import AzureBlobStorageService
from core.analyze import ImageAnalyzer
from core.config import settings
from core.instructions import (analyze_image_system_message,
                                       img_prompt_enhance_msg,
                                       brand_protect_replace_msg,
                                       brand_protect_neutralize_msg,
                                       filename_system_message
)

router = APIRouter()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest):
    """Generate an image based on the provided prompt and settings"""
    try:
        # Prepare parameters based on request
        params = {
            "prompt": request.prompt,
            "model": request.model,
            "n": request.n,
            "size": request.size,
        }

        # Add gpt-image-1 specific parameters if applicable
        if request.model == "gpt-image-1":
            if request.quality:
                params["quality"] = request.quality
            if request.background != "auto":
                params["background"] = request.background
            if request.output_format != "png":
                params["output_format"] = request.output_format
            if request.output_format in ["webp", "jpeg"] and request.output_compression != 100:
                params["output_compression"] = request.output_compression
            if request.moderation != "auto":
                params["moderation"] = request.moderation
            if request.user:
                params["user"] = request.user

            logger.info(
                f"Generating image with gpt-image-1, quality: {request.quality}, size: {request.size}")

        # Generate image
        response = dalle_client.generate_image(**params)

        # Create token usage information if available
        token_usage = None
        if "usage" in response:
            input_tokens_details = None
            if "input_tokens_details" in response["usage"]:
                input_tokens_details = InputTokensDetails(
                    text_tokens=response["usage"]["input_tokens_details"].get(
                        "text_tokens", 0),
                    image_tokens=response["usage"]["input_tokens_details"].get(
                        "image_tokens", 0)
                )

            token_usage = TokenUsage(
                total_tokens=response["usage"].get("total_tokens", 0),
                input_tokens=response["usage"].get("input_tokens", 0),
                output_tokens=response["usage"].get("output_tokens", 0),
                input_tokens_details=input_tokens_details
            )

            # Log token usage for cost tracking
            logger.info(
                f"Token usage - Total: {token_usage.total_tokens}, Input: {token_usage.input_tokens}, Output: {token_usage.output_tokens}")

        return ImageGenerationResponse(
            success=True,
            message="Refer to the imgen_model_response for details",
            imgen_model_response=response,
            token_usage=token_usage
        )
    except Exception as e:
        logger.error(f"Error in /generate endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edit", response_model=ImageGenerationResponse)
async def edit_image(request: ImageEditRequest):
    """Edit an input image based on the provided prompt, mask image and settings"""
    try:
        # Validate file size for all images
        max_file_size_mb = settings.GPT_IMAGE_MAX_FILE_SIZE_MB

        # Prepare parameters based on request
        params = {
            "prompt": request.prompt,
            "model": request.model,
            "n": request.n,
            "size": request.size,
            "image": request.image,
        }

        # Add mask if provided
        if request.mask:
            params["mask"] = request.mask

        # Add gpt-image-1 specific parameters if applicable
        if request.model == "gpt-image-1":
            if request.quality:
                params["quality"] = request.quality
            if request.output_format != "png":
                params["output_format"] = request.output_format
            if request.output_format in ["webp", "jpeg"] and request.output_compression != 100:
                params["output_compression"] = request.output_compression
            if request.user:
                params["user"] = request.user

            # Log information about multiple images if applicable
            if isinstance(request.image, list):
                image_count = len(request.image)
                logger.info(
                    f"Editing with {image_count} reference images using gpt-image-1, quality: {request.quality}, size: {request.size}")

                # Check if organization is verified when using multiple images
                if image_count > 1 and not settings.OPENAI_ORG_VERIFIED:
                    logger.warning(
                        "Using multiple reference images requires organization verification")
            else:
                logger.info(
                    f"Editing single image using gpt-image-1, quality: {request.quality}, size: {request.size}")

        # Perform image editing
        response = dalle_client.edit_image(**params)

        # Create token usage information if available
        token_usage = None
        if "usage" in response:
            input_tokens_details = None
            if "input_tokens_details" in response["usage"]:
                input_tokens_details = InputTokensDetails(
                    text_tokens=response["usage"]["input_tokens_details"].get(
                        "text_tokens", 0),
                    image_tokens=response["usage"]["input_tokens_details"].get(
                        "image_tokens", 0)
                )

            token_usage = TokenUsage(
                total_tokens=response["usage"].get("total_tokens", 0),
                input_tokens=response["usage"].get("input_tokens", 0),
                output_tokens=response["usage"].get("output_tokens", 0),
                input_tokens_details=input_tokens_details
            )

            # Log token usage for cost tracking
            logger.info(
                f"Token usage - Total: {token_usage.total_tokens}, Input: {token_usage.input_tokens}, Output: {token_usage.output_tokens}")

        return ImageGenerationResponse(
            success=True,
            message="Refer to the imgen_model_response for details",
            imgen_model_response=response,
            token_usage=token_usage
        )
    except Exception as e:
        logger.error(f"Error in /edit endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edit/upload", response_model=ImageGenerationResponse)
async def edit_image_upload(
    prompt: str = Form(...),
    model: str = Form("gpt-image-1"),
    n: int = Form(1),
    size: str = Form("auto"),
    quality: str = Form("auto"),
    output_format: str = Form("png"),
    image: List[UploadFile] = File(...),
    mask: Optional[UploadFile] = File(None)
):
    """Edit input images uploaded via multipart form data"""
    try:
        # Log request info
        logger.info(
            f"Received {len(image)} image(s) for editing with prompt: {prompt}")

        # Validate file size for all images
        max_file_size_mb = settings.GPT_IMAGE_MAX_FILE_SIZE_MB
        temp_files = []

        try:
            # Process each uploaded image
            image_file_objs = []
            for idx, img in enumerate(image):
                # Check file size
                contents = await img.read()
                file_size_mb = len(contents) / (1024 * 1024)
                if file_size_mb > max_file_size_mb:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Image {idx+1} exceeds maximum size of {max_file_size_mb}MB"
                    )

                # Create a temporary file with the right extension based on content type
                content_type = img.content_type or "image/png"
                ext = content_type.split("/")[-1]
                if ext not in ["jpeg", "jpg", "png", "webp"]:
                    # Try to determine the format from the file data
                    try:
                        with Image.open(io.BytesIO(contents)) as pil_img:
                            ext = pil_img.format.lower() if pil_img.format else "png"
                    except Exception:
                        ext = "png"  # Default to PNG if we can't determine format

                # Ensure proper extension
                if ext == "jpg":
                    ext = "jpeg"

                # Create a named temporary file with the correct extension
                temp_fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
                temp_files.append((temp_fd, temp_path))

                # Write the contents and close the file descriptor
                with os.fdopen(temp_fd, 'wb') as f:
                    f.write(contents)

                # Store the file path for the API call
                image_file_objs.append(temp_path)

                logger.info(
                    f"Saved image {idx+1} to {temp_path} with format {ext}")

            # Process mask if provided
            mask_file_obj = None
            if mask:
                mask_contents = await mask.read()

                # Determine mask format
                mask_content_type = mask.content_type or "image/png"
                mask_ext = mask_content_type.split("/")[-1]
                if mask_ext not in ["jpeg", "jpg", "png", "webp"]:
                    # Try to determine the format from the file data
                    try:
                        with Image.open(io.BytesIO(mask_contents)) as pil_img:
                            mask_ext = pil_img.format.lower() if pil_img.format else "png"
                    except Exception:
                        mask_ext = "png"  # Default to PNG

                # Ensure proper extension
                if mask_ext == "jpg":
                    mask_ext = "jpeg"

                # Create a named temporary file for the mask
                mask_fd, mask_path = tempfile.mkstemp(suffix=f".{mask_ext}")
                temp_files.append((mask_fd, mask_path))

                # Write the mask contents
                with os.fdopen(mask_fd, 'wb') as f:
                    f.write(mask_contents)

                mask_file_obj = mask_path
                logger.info(
                    f"Saved mask to {mask_path} with format {mask_ext}")

            # Prepare parameters for the OpenAI API call
            logger.info(
                f"Editing {len(image_file_objs)} image(s) using {model}, quality: {quality}, size: {size}")

            # Create a dictionary of parameters for the API call
            params = {
                "prompt": prompt,
                "model": model,
                "n": n,
                "size": size,
            }

            # Add quality parameter for gpt-image-1
            if model == "gpt-image-1":
                params["quality"] = quality
                # Note: output_format is not supported for image editing in the OpenAI API
                # Keeping this commented to document the limitation
                # if output_format != "png":
                #     params["output_format"] = output_format

            # Make the API call with proper file objects
            # The OpenAI SDK expects image parameter to be a file-like object opened in binary mode
            if len(image_file_objs) == 1:
                # Single image case
                with open(image_file_objs[0], "rb") as image_file:
                    params["image"] = image_file

                    # Add mask if provided
                    if mask_file_obj:
                        with open(mask_file_obj, "rb") as mask_file:
                            params["mask"] = mask_file
                            response = dalle_client.edit_image(**params)
                    else:
                        response = dalle_client.edit_image(**params)
            else:
                # Multiple images case (only for gpt-image-1)
                # For multiple files, we need to open them one by one
                # This is a bit complicated because we need to have all files open simultaneously
                # Create a list to hold all open file handles to close them later
                open_files = []
                try:
                    image_files = []
                    for path in image_file_objs:
                        f = open(path, "rb")
                        open_files.append(f)
                        image_files.append(f)

                    params["image"] = image_files

                    # Add mask if provided
                    if mask_file_obj:
                        mask_f = open(mask_file_obj, "rb")
                        open_files.append(mask_f)
                        params["mask"] = mask_f

                    response = dalle_client.edit_image(**params)
                finally:
                    # Close all open file handles
                    for f in open_files:
                        f.close()

            # Process response and create token usage info
            token_usage = None
            if "usage" in response:
                input_tokens_details = None
                if "input_tokens_details" in response["usage"]:
                    input_tokens_details = InputTokensDetails(
                        text_tokens=response["usage"]["input_tokens_details"].get(
                            "text_tokens", 0),
                        image_tokens=response["usage"]["input_tokens_details"].get(
                            "image_tokens", 0)
                    )

                token_usage = TokenUsage(
                    total_tokens=response["usage"].get("total_tokens", 0),
                    input_tokens=response["usage"].get("input_tokens", 0),
                    output_tokens=response["usage"].get("output_tokens", 0),
                    input_tokens_details=input_tokens_details
                )

                # Log token usage for cost tracking
                logger.info(
                    f"Token usage - Total: {token_usage.total_tokens}, Input: {token_usage.input_tokens}, Output: {token_usage.output_tokens}"
                )

            return ImageGenerationResponse(
                success=True,
                message="Refer to the imgen_model_response for details",
                imgen_model_response=response,
                token_usage=token_usage
            )

        finally:
            # Cleanup temporary files
            for fd, path in temp_files:
                try:
                    # The file descriptor is already closed, just remove the file
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    logger.warning(
                        f"Failed to remove temp file {path}: {str(e)}")

    except Exception as e:
        logger.error(
            f"Error in /edit/upload endpoint: {str(e)}", exc_info=True)
        # Provide more explicit errors for debugging
        error_detail = str(e)
        if isinstance(e, HTTPException):
            error_detail = e.detail
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/save", response_model=ImageSaveResponse)
async def save_generated_images(
    request: ImageSaveRequest,
    azure_storage_service: AzureBlobStorageService = Depends(
        lambda: AzureBlobStorageService())
):
    """
    Save generated images to blob storage

    Takes the output from the generate endpoint, converts base64 images to files,
    and uploads them to Azure Blob Storage.
    """
    try:
        # Check if we have a valid generation response
        if not request.generation_response or not request.generation_response.imgen_model_response:
            raise HTTPException(
                status_code=400, detail="No valid image generation response provided")

        # Extract image data from the generation response
        images_data = request.generation_response.imgen_model_response.get("data", [
        ])
        if not images_data:
            raise HTTPException(
                status_code=400, detail="No images found in the generation response")

        # Process only the first image if save_all is False
        if not request.save_all:
            images_data = [images_data[0]]

        # Prepare metadata
        metadata = {}
        if request.prompt:
            metadata["prompt"] = request.prompt
        if request.model:
            metadata["model"] = request.model
            # Add gpt-image-1 specific metadata
            if request.model == "gpt-image-1" and hasattr(request, "quality"):
                metadata["quality"] = request.quality
            if request.model == "gpt-image-1" and hasattr(request, "background"):
                metadata["background"] = request.background
        if request.size:
            metadata["size"] = request.size

        # Convert and save each image
        saved_images = []
        for idx, img_data in enumerate(images_data):
            img_file = None
            filename = None

            # Handle different response formats (url or b64_json)
            if "b64_json" in img_data:
                # Decode base64 image
                image_bytes = base64.b64decode(img_data["b64_json"])

                # Create a file-like object
                img_file = io.BytesIO(image_bytes)

                # Use PIL to determine image format and handle transparent background
                with Image.open(img_file) as img:
                    img_format = img.format or "PNG"
                    has_transparency = img.mode == 'RGBA' and 'A' in img.getbands()

                    if has_transparency:
                        metadata["has_transparency"] = "true"
                        # Ensure PNG format for transparent images
                        if img_format.upper() != "PNG":
                            img_format = "PNG"
                            img_file = io.BytesIO()
                            img.save(img_file, format="PNG")

                # Reset file pointer
                img_file.seek(0)

                # Create filename
                quality_suffix = f"_{request.quality}" if request.model == "gpt-image-1" and hasattr(
                    request, "quality") else ""
                filename = f"generated_image_{idx+1}{quality_suffix}.{img_format.lower()}"

            elif "url" in img_data:
                # Download image from URL
                response = requests.get(img_data["url"])
                if response.status_code != 200:
                    logger.error(
                        f"Failed to download image from URL: {img_data['url']}")
                    continue

                # Create a file-like object
                img_file = io.BytesIO(response.content)

                # Determine content type and file extension
                content_type = response.headers.get(
                    "Content-Type", "image/png")
                ext = content_type.split("/")[-1]

                # Check if image has transparency using PIL
                with Image.open(img_file) as img:
                    has_transparency = img.mode == 'RGBA' and 'A' in img.getbands()
                    if has_transparency:
                        metadata["has_transparency"] = "true"

                # Reset file pointer
                img_file.seek(0)

                # Create filename
                quality_suffix = f"_{request.quality}" if request.model == "gpt-image-1" and hasattr(
                    request, "quality") else ""
                filename = f"generated_image_{idx+1}{quality_suffix}.{ext}"
            else:
                logger.warning(
                    f"Unsupported image data format for image {idx+1}")
                continue

            if img_file and filename:
                # Add index metadata
                img_metadata = metadata.copy()
                img_metadata["image_index"] = str(idx + 1)
                img_metadata["total_images"] = str(len(images_data))

                # Create a FastAPI UploadFile object
                file = UploadFile(filename=filename, file=img_file)

                # Upload to Azure Blob Storage
                result = await azure_storage_service.upload_asset(
                    file,
                    MediaType.IMAGE.value,
                    metadata=img_metadata,
                    folder_path=request.folder_path
                )

                # Add to saved images
                saved_images.append(result)

                # Close the file
                await file.close()

        # Return the response
        return ImageSaveResponse(
            success=True,
            message=f"Successfully saved {len(saved_images)} images to blob storage",
            saved_images=saved_images,
            total_saved=len(saved_images),
            prompt=request.prompt
        )

    except Exception as e:
        logger.error(f"Error saving generated images: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error saving generated images: {str(e)}"
        )


@router.post("/list", response_model=ImageListResponse)
async def list_images(request: ImageListRequest):
    """List generated images with pagination"""
    try:
        # TODO: Implement image listing:
        # - Get images from storage
        # - Apply pagination
        # - Add image URLs and metadata

        return ImageListResponse(
            success=True,
            images=[],
            total=0,
            limit=request.limit,
            offset=request.offset
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
            image_id=request.image_id
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
            logger.info(f"Downloading image for analysis from: {file_path}")
            response = requests.get(file_path, timeout=30)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to download image: HTTP {response.status_code}"
                )

            # Get image content from response
            image_content = response.content

        # Option 2: Process from base64 string
        elif req.base64_image:
            logger.info("Processing image from base64 data")
            try:
                # Decode base64 to binary
                image_content = base64.b64decode(req.base64_image)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid base64 image data: {str(e)}"
                )

        # Process the image with PIL to handle transparency properly
        try:
            # Open the image with PIL
            with Image.open(io.BytesIO(image_content)) as img:
                # Check if it's a transparent PNG
                has_transparency = img.mode == 'RGBA' and 'A' in img.getbands()

                if has_transparency:
                    logger.info(
                        "Image has transparency, converting for analysis")
                    # Create a white background
                    background = Image.new(
                        'RGBA', img.size, (255, 255, 255, 255))
                    # Paste the image on the background
                    background.paste(img, (0, 0), img)
                    # Convert to RGB (remove alpha channel)
                    background = background.convert('RGB')

                    # Save to bytes
                    img_byte_arr = io.BytesIO()
                    background.save(img_byte_arr, format='JPEG')
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()

                # Also try to resize if the image is very large (LLM models have token limits)
                # This is optional but can help with very large images
                width, height = img.size
                if width > 1500 or height > 1500:
                    logger.info(
                        f"Image is large ({width}x{height}), resizing for analysis")
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
                        img_byte_arr, format='JPEG' if resized_img.mode == 'RGB' else 'PNG')
                    img_byte_arr.seek(0)
                    image_content = img_byte_arr.getvalue()
        except Exception as img_error:
            logger.error(f"Error processing image with PIL: {str(img_error)}")
            # If PIL processing fails, continue with the original image

        # Convert to base64
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        # Remove data URL prefix if present
        image_base64 = re.sub(r"^data:image/.+;base64,", "", image_base64)

        # analyze the image using the LLM
        logger.info("Sending image to LLM for analysis")
        image_analyzer = ImageAnalyzer(llm_client, settings.LLM_DEPLOYMENT)
        insights = image_analyzer.image_chat(
            image_base64, analyze_image_system_message)

        description = insights.get('description')
        products = insights.get('products')
        tags = insights.get('tags')
        feedback = insights.get('feedback')

        return ImageAnalyzeResponse(description=description, products=products, tags=tags, feedback=feedback)

    except Exception as e:
        logger.error(f"Error analyzing image: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing image: {str(e)}"
        )


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
                detail="LLM service is currently unavailable. Please check your environment configuration."
            )

        original_prompt = req.original_prompt
        # Call the LLM to enhance the prompt
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": original_prompt},
        ]
        response = llm_client.chat.completions.create(messages=messages,
                                                      model=settings.LLM_DEPLOYMENT,
                                                      response_format={"type": "json_object"})
        enhanced_prompt = json.loads(
            response.choices[0].message.content).get('prompt')
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
                logger.info(f"Replace competitor brands of: {req.brands_to_protect}")
                system_message = brand_protect_replace_msg.format(brands=req.brands_to_protect)
            elif req.protection_mode == "neutralize":
                logger.info(f"Neutralize competitor brands of: {req.brands_to_protect}")
                system_message = brand_protect_neutralize_msg.format(brands=req.brands_to_protect)       
        else:
            logger.info(f"No brand protection specified.")
            return ImagePromptBrandProtectionResponse(enhanced_prompt=req.original_prompt)

        # Ensure LLM client is available
        if llm_client is None:
            raise HTTPException(
                status_code=503,
                detail="LLM service is currently unavailable. Please check your environment configuration."
            )

        original_prompt = req.original_prompt
        # Call the LLM to enhance the prompt
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": original_prompt},
        ]
        response = llm_client.chat.completions.create(messages=messages,
                                                      model=settings.LLM_DEPLOYMENT,
                                                      response_format={"type": "json_object"})
        enhanced_prompt = json.loads(
            response.choices[0].message.content).get('prompt')
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
                detail="LLM service is currently unavailable. Please check your environment configuration."
            )

        # Validate prompt
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="Prompt must not be empty."
            )

        # Call the LLM to enhance the prompt
        messages = [
            {"role": "system", "content": filename_system_message},
            {"role": "user", "content": req.prompt},
        ]
        response = llm_client.chat.completions.create(
            messages=messages,
            model=settings.LLM_DEPLOYMENT,
            response_format={"type": "json_object"}
        )
        filename = json.loads(
            response.choices[0].message.content).get('filename_prefix')

        # Validate and sanitize filename
        if not filename or not filename.strip():
            raise HTTPException(
                status_code=500,
                detail="Failed to generate a valid filename prefix."
            )
        # Remove invalid characters for most filesystems
        filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', filename.strip())

        # add a sort unique identifier to the filename
        uid = uuid.uuid4()
        short_uid = base64.urlsafe_b64encode(
            uid.bytes).rstrip(b'=').decode('ascii')
        filename += f"_{short_uid}"

        if req.extension:
            ext = req.extension.lstrip('.')
            filename += f".{ext}"

        return ImageFilenameGenerateResponse(filename=filename)

    except Exception as e:
        logger.error(f"Error generating filename: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
