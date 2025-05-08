import os
import logging
import base64
import uuid
import io
import tempfile
import requests
from typing import List, Union, Optional, Dict, Any
from openai import OpenAI, AzureOpenAI
from PIL import Image
from core.config import settings

from tempfile import SpooledTemporaryFile

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GPTImageClient:
    """
    Client for GPT-Image-1 generation and editing using the official OpenAI or Azure OpenAI Python client.
    """

    def __init__(self, api_key: Optional[str] = None, organization_id: Optional[str] = None, provider: Optional[str] = None):
        """
        Initialize the GPT Image client with either OpenAI or Azure OpenAI client

        Args:
            api_key: The API key to use (optional, will use from settings if not provided)
            organization_id: The organization ID for OpenAI (optional)
            provider: The provider to use ('openai' or 'azure', defaults to settings.MODEL_PROVIDER)
        """
        provider = provider or settings.MODEL_PROVIDER

        if provider.lower() == "azure":
            # Use Azure OpenAI
            if not settings.IMAGEGEN_AOAI_RESOURCE or not settings.IMAGEGEN_AOAI_API_KEY:
                raise ValueError(
                    "IMAGEGEN_AOAI_RESOURCE and IMAGEGEN_AOAI_API_KEY must be set for Azure OpenAI")

            self.api_key = settings.IMAGEGEN_AOAI_API_KEY
            self.client = AzureOpenAI(
                azure_endpoint=f"https://{settings.IMAGEGEN_AOAI_RESOURCE}.openai.azure.com/",
                api_key=self.api_key,
                api_version=settings.AOAI_API_VERSION
            )
            # Set deployment name for later use
            self.deployment_name = settings.IMAGEGEN_DEPLOYMENT
            self.provider = "azure"
            logger.info(
                "Initialized GPT-Image-1 client with Azure OpenAI Python SDK")
        else:
            # Use direct OpenAI
            self.api_key = api_key or settings.OPENAI_API_KEY
            if not self.api_key:
                raise ValueError("API key must be provided for OpenAI")

            self.client = OpenAI(
                api_key=self.api_key,
                organization=organization_id or settings.OPENAI_ORG_ID
            )
            self.provider = "openai"
            logger.info(
                "Initialized GPT-Image-1 client with OpenAI Python SDK")

    def generate_image(self, prompt: str, model: str = None, n: int = 1,
                       size: str = "auto", response_format: str = "b64_json",
                       quality: str = "auto", background: str = "auto",
                       output_format: str = "png", output_compression: int = 100,
                       moderation: str = "auto", user: str = None) -> dict:
        """
        Generate images using the model

        Args:
            prompt: A text description of the desired image (max 32000 chars for gpt-image-1)
            model: The model to use for image generation (defaults to IMAGEGEN_DEPLOYMENT for Azure or gpt-image-1 for OpenAI)
            n: The number of images to generate (1-10)
            size: The size of the generated images
            response_format: The format in which the generated images are returned
            quality: The quality of the image generation (low, medium, high, auto)
            background: Background setting (transparent, opaque, auto)
            output_format: Output format (png, webp, jpeg)
            output_compression: Compression rate percentage for webp and jpeg (0-100)
            moderation: Moderation strictness (auto, low)
            user: A unique identifier for tracking and abuse prevention

        Returns:
            A dictionary containing the generated images and token usage
        """
        try:
            # Create a parameter dictionary with all supported parameters
            params = {
                "prompt": prompt,
                "n": n,
                "size": size,
                "quality": quality,
            }

            # Use the appropriate model parameter based on provider
            if self.provider == "azure":
                if not self.deployment_name:
                    raise ValueError(
                        "IMAGEGEN_DEPLOYMENT must be set for Azure OpenAI")
                params["model"] = self.deployment_name
            else:
                params["model"] = model or "gpt-image-1"

            # Add user parameter if provided
            if user:
                params["user"] = user

            # Add gpt-image-1 specific parameters that are supported by the client
            if model == "gpt-image-1":
                # Include background parameter regardless of provider
                if background != "auto":
                    params["background"] = background

                # Add other parameters as they become supported by the client
                try:
                    # These will only work if the client supports them
                    if output_format != "png":
                        params["output_format"] = output_format
                    if output_format in ["webp", "jpeg"] and output_compression != 100:
                        params["output_compression"] = output_compression
                    if moderation != "auto":
                        params["moderation"] = moderation
                except Exception as e:
                    logger.warning(
                        f"Some parameters may not be supported by the current client version: {str(e)}")

            logger.info(
                f"Generating {n} image(s) with provider {self.provider}, model: {params['model']}, quality: {quality}, size: {size}")

            # Make the API call
            response = self.client.images.generate(**params)

            # Format the response to match our expected format
            formatted_response = {
                "created": response.created,
                "data": []
            }

            # Extract token usage if available (for gpt-image-1 only)
            if hasattr(response, "usage"):
                formatted_response["usage"] = {
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                    "input_tokens": getattr(response.usage, "input_tokens", 0),
                    "output_tokens": getattr(response.usage, "output_tokens", 0),
                }

                # Extract detailed input token information if available
                if hasattr(response.usage, "input_tokens_details"):
                    formatted_response["usage"]["input_tokens_details"] = {
                        "text_tokens": getattr(response.usage.input_tokens_details, "text_tokens", 0),
                        "image_tokens": getattr(response.usage.input_tokens_details, "image_tokens", 0)
                    }

            for image in response.data:
                image_data = {}
                if hasattr(image, "url") and image.url:
                    image_data["url"] = image.url
                if hasattr(image, "b64_json") and image.b64_json:
                    image_data["b64_json"] = image.b64_json
                if hasattr(image, "revised_prompt") and image.revised_prompt:
                    image_data["revised_prompt"] = image.revised_prompt

                formatted_response["data"].append(image_data)

            return formatted_response

        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            raise

    def edit_image(self, **kwargs):
        """
        Edit an image based on the provided prompt, mask (optional), and settings

        For Azure OpenAI, this will use the REST API since the Python SDK doesn't support edits
        For direct OpenAI, this will use the model provided or default to gpt-image-1
        """
        try:
            # Extract key parameters for easier access
            prompt = kwargs.get("prompt")
            image = kwargs.get("image")
            mask = kwargs.get("mask")
            n = kwargs.get("n", 1)
            size = kwargs.get("size", "auto")
            quality = kwargs.get("quality", "auto")

            # Azure OpenAI requires REST API for image edits
            if self.provider == "azure":
                if not self.deployment_name:
                    raise ValueError(
                        "IMAGEGEN_DEPLOYMENT must be set for Azure OpenAI")

                # Prepare the URL for the REST API - exactly as in the notebook
                url = f"https://{settings.IMAGEGEN_AOAI_RESOURCE}.openai.azure.com/openai/deployments/{self.deployment_name}/images/edits?api-version={settings.AOAI_API_VERSION}"

                # Prepare headers with API key - exactly as in the notebook
                headers = {
                    "api-key": self.api_key
                }

                # Prepare files dictionary exactly as in the notebook
                files = {}

                # Handle single image or multiple images in the same way as notebook
                if isinstance(image, list):
                    # Multiple images case - following notebook pattern for image[]
                    files = [("image[]", img) for img in image]
                else:
                    # Single image case
                    files["image"] = image

                # Add mask if provided
                if mask:
                    files["mask"] = mask

                # Prepare data dictionary with parameters exactly as notebook does
                data = {
                    "prompt": prompt,
                }

                # Add n if not default
                if n != 1:
                    data["n"] = n

                # Add size if not default
                if size != "auto":
                    data["size"] = size

                # Add quality if not auto
                if quality != "auto":
                    data["quality"] = quality

                # Add any other supported parameters (excluding image/mask which are in files)
                for key, value in kwargs.items():
                    if key not in ["prompt", "image", "mask", "n", "size", "quality", "model"] and value is not None:
                        data[key] = value

                logger.info(
                    f"Editing image with Azure REST API, deployment: {self.deployment_name}, "
                    f"{'multiple' if isinstance(image, list) else 'single'} image(s), "
                    f"quality: {quality}, size: {size}"
                )

                # Send the request
                response = requests.post(
                    url, headers=headers, files=files, data=data)
                response.raise_for_status()

                # Parse the response
                return response.json()
            else:
                # Handle model parameter for OpenAI provider
                if "model" not in kwargs:
                    kwargs["model"] = "gpt-image-1"

                # Get model for logging
                model = kwargs.get("model")

                # Log request details
                logger.info(
                    f"Editing image with OpenAI SDK, model {model}, "
                    f"{len(kwargs.get('image', [])) if isinstance(kwargs.get('image', []), list) else '1'} "
                    f"reference image(s), quality: {kwargs.get('quality', 'auto')}, size: {size}"
                )

                # Call the OpenAI API to edit the image
                response = self.client.images.edit(**kwargs)
                return response.model_dump()

        except Exception as e:
            logger.error(f"Error editing image: {str(e)}")
            raise

    async def process_edit_image_upload(self, prompt: str, model: str = None, n: int = 1, size: str = "auto",
                                        quality: str = "auto", image_files: List[SpooledTemporaryFile] = None,
                                        mask_file: Optional[SpooledTemporaryFile] = None):
        """
        Process uploaded image files for editing.

        Args:
            prompt: Text prompt for image editing
            model: Model to use (defaults to IMAGEGEN_DEPLOYMENT for Azure or gpt-image-1 for OpenAI)
            n: Number of images to generate
            size: Image size
            quality: Image quality
            image_files: List of uploaded image files
            mask_file: Optional mask file for editing

        Returns:
            The response from the image editing API
        """
        # Validate file size for all images
        max_file_size_mb = 4  # Default to 4MB if not specified in settings
        temp_files = []

        try:
            # Process each uploaded image
            image_file_objs = []
            for idx, img_file in enumerate(image_files):
                # Check file size
                img_file.seek(0, 2)  # Seek to end
                file_size_mb = img_file.tell() / (1024 * 1024)
                img_file.seek(0)  # Reset pointer to beginning

                if file_size_mb > max_file_size_mb:
                    raise ValueError(
                        f"Image {idx+1} exceeds maximum size of {max_file_size_mb}MB")

                # Read image content
                contents = img_file.read()

                # Determine file format
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
            if mask_file:
                # Read mask content
                mask_file.seek(0)
                mask_contents = mask_file.read()

                # Determine mask format
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

            # Prepare parameters for the API call
            logger.info(
                f"Editing {len(image_file_objs)} image(s) using provider {self.provider}, model: {model or self.deployment_name}, quality: {quality}, size: {size}")

            # Create a dictionary of parameters for the API call
            params = {
                "prompt": prompt,
                "n": n,
                "size": size,
            }

            # Use the appropriate model parameter based on provider
            if self.provider == "azure":
                if not self.deployment_name:
                    raise ValueError(
                        "IMAGEGEN_DEPLOYMENT must be set for Azure OpenAI")
                params["model"] = self.deployment_name
            else:
                params["model"] = model or "gpt-image-1"

            # Add quality parameter
            if quality != "auto":
                params["quality"] = quality

            # For Azure provider, we need to use the REST API directly
            if self.provider == "azure":
                # Prepare the URL for the REST API
                url = f"https://{settings.IMAGEGEN_AOAI_RESOURCE}.openai.azure.com/openai/deployments/{self.deployment_name}/images/edits?api-version={settings.AOAI_API_VERSION}"

                # Prepare headers with API key
                headers = {
                    "api-key": self.api_key
                }

                # Prepare files exactly as the notebook does
                files = {}

                # Handle multiple images vs single image
                if len(image_file_objs) > 1:
                    # Multiple images - for REST API, following notebook pattern
                    files = [("image[]", open(path, "rb"))
                             for path in image_file_objs]
                else:
                    # Single image - for REST API, following notebook pattern
                    files = {
                        "image": open(image_file_objs[0], "rb")
                    }

                # Add mask if provided, exactly as notebook does
                if mask_file_obj:
                    files["mask"] = open(mask_file_obj, "rb")

                # Prepare data dictionary with parameters, exactly as notebook does
                data = {
                    "prompt": prompt
                }

                # Add n if not default
                if n != 1:
                    data["n"] = n

                # Add size if not default
                if size != "auto":
                    data["size"] = size

                # Add quality if not auto
                if quality != "auto":
                    data["quality"] = quality

                logger.info(
                    f"Editing image with Azure REST API, deployment: {self.deployment_name}, "
                    f"using {len(image_file_objs)} image(s), quality: {quality}, size: {size}"
                )

                try:
                    # Send the request
                    response = requests.post(
                        url, headers=headers, files=files, data=data)
                    response.raise_for_status()

                    # Return the JSON response
                    return response.json()
                finally:
                    # No need to explicitly close files - requests will handle it
                    pass
            else:
                # OpenAI SDK approach (original implementation)
                # Make the API call with proper file objects
                if len(image_file_objs) == 1:
                    # Single image case
                    with open(image_file_objs[0], "rb") as image_file:
                        params["image"] = image_file

                        # Add mask if provided
                        if mask_file_obj:
                            with open(mask_file_obj, "rb") as mask_file:
                                params["mask"] = mask_file
                                response = self.edit_image(**params)
                        else:
                            response = self.edit_image(**params)
                else:
                    # Multiple images case (only for gpt-image-1)
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

                        response = self.edit_image(**params)
                    finally:
                        # Close all open file handles
                        for f in open_files:
                            f.close()

                return response
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


# Alias to maintain backward compatibility during migration
DALLEClient = GPTImageClient
