import httpx
import os
import logging
import io
from typing import List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_sora2_response_to_job_format(sora2_response):
    """
    Convert Sora 2 API response to the expected job format.
    
    Sora 2 returns: {id, status, progress, size, seconds, prompt, model, ...}
    Expected format: {id, status, prompt, n_variants, n_seconds, height, width, generations, ...}
    """
    # Map Sora 2 status to expected format
    status_map = {
        "queued": "queued",
        "in_progress": "processing",
        "completed": "succeeded",
        "failed": "failed"
    }
    sora2_status = sora2_response.get("status", "queued")
    mapped_status = status_map.get(sora2_status, sora2_status)
    
    result = {
        "id": sora2_response.get("id"),
        "status": mapped_status,
        "prompt": sora2_response.get("prompt", ""),
        "n_variants": 1,  # Sora 2 always generates 1 video
        "model": sora2_response.get("model", "sora-2"),
    }
    
    # Convert size string "WIDTHxHEIGHT" to width and height
    size = sora2_response.get("size", "720x1280")
    if "x" in size:
        width_str, height_str = size.split("x")
        result["width"] = int(width_str)
        result["height"] = int(height_str)
    else:
        result["width"] = 1280
        result["height"] = 720
    
    # Convert seconds string to int
    seconds_str = sora2_response.get("seconds", "4")
    result["n_seconds"] = int(seconds_str) if isinstance(
        seconds_str, str) else seconds_str
    
    # Add timestamps
    result["created_at"] = sora2_response.get("created_at")
    result["finished_at"] = sora2_response.get("completed_at")
    
    # Add error info
    error = sora2_response.get("error")
    if error:
        result["failure_reason"] = str(
            error) if isinstance(error, dict) else error
    else:
        result["failure_reason"] = None
    
    # Add generations list - Sora 2 returns the video directly when completed
    # For compatibility, create a generations list
    if mapped_status == "succeeded" and sora2_response.get("id"):
        result["generations"] = [{
            "id": sora2_response.get("id"),
            "prompt": sora2_response.get("prompt", ""),
            "status": "succeeded"
        }]
    else:
        result["generations"] = []
    
    # Add Sora 2 specific fields
    result["has_audio"] = True  # Sora 2 always includes audio
    result["is_remix"] = sora2_response.get(
        "remixed_from_video_id") is not None
    result["remixed_from_video_id"] = sora2_response.get(
        "remixed_from_video_id")
    result["progress"] = sora2_response.get("progress", 0)
    
    return result


class Sora:
    """Async Sora 2 client using httpx for non-blocking HTTP requests."""

    SUPPORTED_SIZES = [
        "1280x720",   # Landscape
        "720x1280",   # Portrait (default)
        "1792x1024",  # Landscape
        "1024x1792",  # Portrait
    ]

    SUPPORTED_DURATIONS = ["4", "8", "12"]

    def __init__(self, resource_name, deployment_name, api_key, api_version=None):
        self.resource_name = resource_name
        self.deployment_name = deployment_name
        self.api_key = api_key
        self.base_url = f"https://{self.resource_name}.openai.azure.com/openai/v1/videos"

        # Important: don't set a default Content-Type on the client.
        # httpx will set the correct Content-Type for JSON and multipart automatically.
        self.headers = {
            "api-key": self.api_key,
        }

        # Lazy-initialized async client
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(
            f"Initialized Sora 2 client with resource: {resource_name}, deployment: {deployment_name}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client (lazy initialization)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers=self.headers
            )
        return self._client

    async def close(self):
        """Close the async client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _validate_size(self, size):
        if size not in self.SUPPORTED_SIZES:
            raise ValueError(
                f"Unsupported video size '{size}'. "
                f"Sora 2 only supports: {', '.join(self.SUPPORTED_SIZES)}"
            )

    def _handle_api_error(self, response: httpx.Response):
        try:
            error_detail = response.json()
            logger.error(f"Sora API error response: {error_detail}")
        except Exception:
            logger.error(
                f"Sora API error: {response.status_code} {response.text}")
        response.raise_for_status()

    async def create_video_generation_job(self, prompt, n_seconds, height, width):
        """
        Create a video generation job with Sora 2.

        Note: Sora 2 always generates exactly 1 video per request.

        Args:
            prompt: Text prompt describing the video to generate
            n_seconds: Duration in seconds (will be converted to 4, 8, or 12 for Sora 2)
            height: Video height in pixels
            width: Video width in pixels
        """
        client = await self._get_client()
        url = self.base_url

        # Convert duration to Sora 2 supported values (must be strings: "4", "8", or "12")
        if n_seconds <= 6:
            seconds = "4"
        elif n_seconds <= 10:
            seconds = "8"
        else:
            seconds = "12"

        size = f"{width}x{height}"
        self._validate_size(size)

        payload = {
            "model": self.deployment_name,
            "prompt": prompt,
            "size": size,
            "seconds": seconds
        }

        logger.info(
            f"Creating Sora 2 video generation job with prompt: {prompt[:50]}... "
            f"(size={size}, seconds={seconds})")

        response = await client.post(url, json=payload)

        if not response.is_success:
            self._handle_api_error(response)

        sora2_response = response.json()
        return convert_sora2_response_to_job_format(sora2_response)

    async def create_video_generation_job_with_images(self, prompt, images, image_filenames, n_seconds, height, width):
        """Create video generation job with image reference using multipart upload (Sora 2).

        Note: Sora 2 only supports a single input_reference image, not multiple images.
        If multiple images are provided, only the first one will be used.
        Sora 2 always generates exactly 1 video per request.

        Args:
            prompt: Text prompt describing the video
            images: List of image byte content (only first image used)
            image_filenames: List of filenames for images
            n_seconds: Duration in seconds (will be converted to 4, 8, or 12)
            height: Video height in pixels
            width: Video width in pixels
        """
        client = await self._get_client()
        url = self.base_url

        # Sora 2 only supports single input_reference, use first image
        if not images or len(images) == 0:
            raise ValueError(
                "At least one image is required for image-to-video generation")
        
        first_image = images[0]
        first_filename = image_filenames[0] if image_filenames else "image.jpg"
        
        # Convert duration to Sora 2 supported values (must be strings: "4", "8", or "12")
        if n_seconds <= 6:
            seconds = "4"
        elif n_seconds <= 10:
            seconds = "8"
        else:
            seconds = "12"

        size = f"{width}x{height}"
        self._validate_size(size)

        multipart_headers = dict(self.headers)

        files = {
            "input_reference": (first_filename, io.BytesIO(first_image), "image/jpeg")
        }

        data = {
            "model": self.deployment_name,
            "prompt": prompt,
            "size": size,
            "seconds": seconds
        }

        logger.info(
            f"Creating Sora 2 video job with image reference: {first_filename}, prompt: {prompt[:50]}...")

        response = await client.post(
            url,
            headers=multipart_headers,
            data=data,
            files=files
        )

        if not response.is_success:
            self._handle_api_error(response)

        sora2_response = response.json()
        return convert_sora2_response_to_job_format(sora2_response)

    async def get_video_generation_job(self, job_id):
        """Get video generation job status (Sora 2 API)."""
        client = await self._get_client()
        url = f"{self.base_url}/{job_id}"
        logger.info(f"Getting video generation job: {job_id}")

        response = await client.get(url)
        response.raise_for_status()

        sora2_response = response.json()
        # Convert to expected format
        return convert_sora2_response_to_job_format(sora2_response)

    async def delete_video_generation_job(self, job_id):
        """Delete a video generation job (Sora 2 API)."""
        client = await self._get_client()
        url = f"{self.base_url}/{job_id}"
        logger.info(f"Deleting video generation job: {job_id}")

        response = await client.delete(url)
        response.raise_for_status()
        return response.status_code

    async def list_video_generation_jobs(self, before=None, after=None, limit=10, statuses=None):
        """List video generation jobs (Sora 2 API)."""
        client = await self._get_client()
        url = self.base_url
        params = {"limit": limit}
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        if statuses:
            params["statuses"] = ",".join(statuses)
        logger.info(f"Listing video generation jobs with params: {params}")

        response = await client.get(url, params=params)
        response.raise_for_status()

        sora2_response = response.json()
        # Sora 2 returns a list directly or wrapped in "data"
        videos = sora2_response.get("data", sora2_response) if isinstance(
            sora2_response, dict) else sora2_response
        if not isinstance(videos, list):
            videos = [videos]
        # Convert each video to expected format
        converted = [convert_sora2_response_to_job_format(
            video) for video in videos]
        return {"data": converted}

    async def get_video_generation_video_content(self, generation_id, file_name, target_folder='videos'):
        """
        Download the video content for a given video ID as an MP4 file (Sora 2 API).

        Args:
            generation_id (str): The video ID (from Sora 2 response).
            file_name (str): The filename to save the video as (include .mp4 extension).
            target_folder (str): The folder to save the video to (default: 'videos').

        Returns:
            str: The path to the downloaded file.
        """
        client = await self._get_client()
        url = f"{self.base_url}/{generation_id}/content"

        # Create directory if it doesn't exist
        os.makedirs(target_folder, exist_ok=True)

        file_path = os.path.join(target_folder, file_name)

        logger.info(
            f"Downloading video content for generation {generation_id} to {file_path}")

        # Stream the download to handle large files
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)

        logger.info(f"Successfully downloaded video to {file_path}")
        return file_path

    async def get_video_generation_gif_content(self, generation_id, file_name, target_folder='gifs'):
        """
        Download the GIF content for a given video ID (Sora 2 API).

        Args:
            generation_id (str): The video ID (from Sora 2 response).
            file_name (str): The filename to save the GIF as.
            target_folder (str): The folder to save the GIF to (default: 'gifs').

        Returns:
            str: The path to the downloaded file.
        """
        client = await self._get_client()
        url = f"{self.base_url}/{generation_id}/content?format=gif"

        # Create directory if it doesn't exist
        os.makedirs(target_folder, exist_ok=True)

        file_path = os.path.join(target_folder, file_name)

        logger.info(
            f"Downloading GIF content for generation {generation_id} to {file_path}")

        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        logger.info(f"Successfully downloaded GIF to {file_path}")
        return file_path

    async def upload_cameo_reference(self, face_image, voice_audio=None):
        """
        Upload a cameo reference (face image and optional voice) for personalized video generation.
        
        Args:
            face_image: Bytes content of the face image
            voice_audio: Optional bytes content of voice audio sample
            
        Returns:
            dict: Cameo reference details including ID
        """
        client = await self._get_client()
        url = f"{self.base_url}/cameo/references"

        multipart_headers = dict(self.headers)
        
        files = [("face", ("face.jpg", io.BytesIO(face_image), "image/jpeg"))]
        if voice_audio:
            files.append(
                ("voice", ("voice.mp3", io.BytesIO(voice_audio), "audio/mpeg")))
        
        logger.info("Uploading cameo reference (face and voice)")
        response = await client.post(url, headers=multipart_headers, files=files)
        response.raise_for_status()
        return response.json()
    
    async def get_cameo_references(self, limit=10):
        """
        List uploaded cameo references.
        
        Args:
            limit: Maximum number of references to return
            
        Returns:
            dict: List of cameo references
        """
        client = await self._get_client()
        url = f"{self.base_url}/cameo/references?limit={limit}"
        logger.info(f"Listing cameo references (limit={limit})")

        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def delete_cameo_reference(self, reference_id):
        """
        Delete a cameo reference.
        
        Args:
            reference_id: ID of the cameo reference to delete
            
        Returns:
            int: HTTP status code
        """
        client = await self._get_client()
        url = f"{self.base_url}/cameo/references/{reference_id}"
        logger.info(f"Deleting cameo reference: {reference_id}")

        response = await client.delete(url)
        response.raise_for_status()
        return response.status_code
    
    async def create_remix_job(self, video_id, prompt, modifications=None):
        """
        Create a remix job to modify an existing video (video-to-video) - Sora 2 API.
        
        Args:
            video_id: ID of the existing video to remix (e.g., "video_...")
            prompt: New prompt or modification instructions
            modifications: Ignored - Sora 2 remix only uses prompt
            
        Returns:
            dict: Remix job details
        """
        client = await self._get_client()
        url = self.base_url
        payload = {
            "model": self.deployment_name,
            "remix_video_id": video_id,
            "prompt": prompt
        }
        
        logger.info(
            f"Creating Sora 2 remix job for video {video_id} with prompt: {prompt[:50]}...")

        response = await client.post(url, json=payload)
        response.raise_for_status()

        sora2_response = response.json()
        # Convert to expected format
        return convert_sora2_response_to_job_format(sora2_response)
