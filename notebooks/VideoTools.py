# Standard Library Imports
import os
import json
import time
import io
import shutil
import random
import base64
import logging
from datetime import timedelta
from typing import List, Dict, Optional
from io import BytesIO

import requests
import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_sora2_response_to_job_format(sora_response: dict) -> dict:
    """
    Convert Sora API response to a consistent job format.

    API returns: {id, status, progress, size, seconds, prompt, model, ...}
    Converted format: {id, status, prompt, n_seconds, height, width, generations, ...}
    """
    # Map API status to expected format
    status_map = {
        "queued": "queued",
        "in_progress": "processing",
        "completed": "succeeded",
        "failed": "failed"
    }
    api_status = sora_response.get("status", "queued")
    mapped_status = status_map.get(api_status, api_status)

    result = {
        "id": sora_response.get("id"),
        "status": mapped_status,
        "prompt": sora_response.get("prompt", ""),
        "model": sora_response.get("model", "sora"),
    }

    # Convert size string "WIDTHxHEIGHT" to width and height
    size = sora_response.get("size", "720x1280")
    if size and "x" in size:
        width_str, height_str = size.split("x")
        result["width"] = int(width_str)
        result["height"] = int(height_str)
    else:
        result["width"] = 720
        result["height"] = 1280

    # Convert seconds string to int
    seconds_str = sora_response.get("seconds", "4")
    result["n_seconds"] = int(seconds_str) if isinstance(
        seconds_str, str) else seconds_str

    # Add timestamps
    result["created_at"] = sora_response.get("created_at")
    result["finished_at"] = sora_response.get("completed_at")
    result["expires_at"] = sora_response.get("expires_at")

    # Add error info
    error = sora_response.get("error")
    if error:
        result["failure_reason"] = str(
            error) if isinstance(error, dict) else error
    else:
        result["failure_reason"] = None

    # Add generations list - create a generations list with the video ID
    if mapped_status == "succeeded" and sora_response.get("id"):
        result["generations"] = [{
            "id": sora_response.get("id"),
            "prompt": sora_response.get("prompt", ""),
            "status": "succeeded"
        }]
    else:
        result["generations"] = []

    # Add additional fields
    result["has_audio"] = True  # Audio is always included
    result["is_remix"] = sora_response.get("remixed_from_video_id") is not None
    result["remixed_from_video_id"] = sora_response.get(
        "remixed_from_video_id")
    result["progress"] = sora_response.get("progress", 0)

    return result


class Sora:
    """
    Sora API client for Azure OpenAI video generation.

    Features:
    - Text-to-video generation
    - Image-to-video generation (input_reference)
    - Video remix (video-to-video transformation)
    - Automatic audio generation

    Supported sizes: 1280x720 (landscape), 720x1280 (portrait, default)
    Supported durations: 4, 8, or 12 seconds
    """

    SUPPORTED_SIZES = [
        "1280x720",   # Landscape
        "720x1280",   # Portrait (default)
    ]

    SUPPORTED_DURATIONS = ["4", "8", "12"]

    def __init__(self, resource_name: str, deployment_name: str, api_key: str, api_version: str = None):
        """
        Initialize the Sora client.

        Args:
            resource_name (str): The Azure OpenAI resource name.
            deployment_name (str): The Sora deployment name.
            api_key (str): The API key.
            api_version (str, optional): Not used (v1 API).
        """
        self.resource_name = resource_name
        self.deployment_name = deployment_name
        self.api_key = api_key
        self.base_url = f"https://{self.resource_name}.openai.azure.com/openai/v1/videos"
        self.headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        logger.info(
            f"Initialized Sora client with resource: {resource_name}, deployment: {deployment_name}")

    def _validate_size(self, size: str) -> None:
        """Validate that the size is supported."""
        if size not in self.SUPPORTED_SIZES:
            raise ValueError(
                f"Unsupported video size '{size}'. "
                f"Supported sizes: {', '.join(self.SUPPORTED_SIZES)}"
            )

    def _convert_duration(self, n_seconds: int) -> str:
        """Convert duration to supported string values (4, 8, or 12)."""
        if n_seconds <= 6:
            return "4"
        elif n_seconds <= 10:
            return "8"
        else:
            return "12"

    def _handle_api_error(self, response: requests.Response) -> None:
        """Log and raise API errors with details."""
        try:
            error_detail = response.json()
            logger.error(f"Sora API error response: {error_detail}")
        except Exception:
            logger.error(
                f"Sora API error: {response.status_code} {response.text}")
        response.raise_for_status()

    def create_video_generation_job(self, prompt: str, n_seconds: int = 8,
                                    height: int = 1280, width: int = 720) -> dict:
        """
        Create a video generation job.

        Audio is automatically generated.

        Args:
            prompt (str): Text prompt describing the video to generate.
            n_seconds (int): Duration in seconds (will be mapped to 4, 8, or 12).
            height (int): Video height in pixels.
            width (int): Video width in pixels.

        Returns:
            dict: Job details with converted format.
        """
        url = self.base_url

        seconds = self._convert_duration(n_seconds)
        size = f"{width}x{height}"
        self._validate_size(size)

        payload = {
            "model": self.deployment_name,
            "prompt": prompt,
            "size": size,
            "seconds": seconds
        }

        logger.info(
            f"Creating video job: prompt='{prompt[:50]}...', size={size}, seconds={seconds}")
        response = requests.post(url, json=payload, headers=self.headers)

        if not response.ok:
            self._handle_api_error(response)

        sora_response = response.json()
        return convert_sora2_response_to_job_format(sora_response)

    def create_video_generation_job_with_image(self, prompt: str, image_path: str = None,
                                               image_bytes: bytes = None,
                                               n_seconds: int = 8,
                                               height: int = 1280, width: int = 720) -> dict:
        """
        Create a video generation job with an input reference image (image-to-video).

        The reference image is used as a visual anchor for the first frame.

        Args:
            prompt (str): Text prompt describing the video to generate.
            image_path (str, optional): Path to the reference image file.
            image_bytes (bytes, optional): Raw bytes of the reference image.
            n_seconds (int): Duration in seconds (will be mapped to 4, 8, or 12).
            height (int): Video height in pixels.
            width (int): Video width in pixels.

        Returns:
            dict: Job details with converted format.
        """
        if not image_path and not image_bytes:
            raise ValueError(
                "Either image_path or image_bytes must be provided")

        url = self.base_url

        seconds = self._convert_duration(n_seconds)
        size = f"{width}x{height}"
        self._validate_size(size)

        # Prepare multipart form data
        multipart_headers = {
            k: v for k, v in self.headers.items() if k.lower() != "content-type"}

        # Load image, resize to match video dimensions, and detect MIME type
        if image_path:
            filename = os.path.basename(image_path)
            img = Image.open(image_path)
            ext = os.path.splitext(filename)[1].lower()
        else:
            filename = "reference.jpg"
            img = Image.open(io.BytesIO(image_bytes))
            ext = ".jpg"

        # Resize image to match requested video size (required by API)
        # Uses letterboxing/pillarboxing to maintain aspect ratio with black padding
        if img.size != (width, height):
            original_size = img.size
            img_width, img_height = img.size

            # Calculate scaling factor to fit within target while maintaining aspect ratio
            scale = min(width / img_width, height / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            # Resize maintaining aspect ratio
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Create black canvas of target size and paste resized image centered
            canvas = Image.new("RGB", (width, height), (0, 0, 0))
            paste_x = (width - new_width) // 2
            paste_y = (height - new_height) // 2

            # Handle images with alpha channel
            if img.mode == "RGBA":
                canvas.paste(img, (paste_x, paste_y), img)
            else:
                canvas.paste(img, (paste_x, paste_y))

            img = canvas
            logger.info(
                f"Resized image from {original_size} to ({width}, {height}) with letterboxing")

        # Convert to bytes with appropriate format
        mime_types = {
            ".jpg": ("image/jpeg", "JPEG"),
            ".jpeg": ("image/jpeg", "JPEG"),
            ".png": ("image/png", "PNG"),
            ".webp": ("image/webp", "WEBP")
        }
        mime_type, img_format = mime_types.get(ext, ("image/jpeg", "JPEG"))

        # Save resized image to bytes
        img_buffer = io.BytesIO()
        img.save(img_buffer, format=img_format)
        img_buffer.seek(0)

        files = {
            "input_reference": (filename, img_buffer, mime_type)
        }

        data = {
            "model": self.deployment_name,
            "prompt": prompt,
            "size": size,
            "seconds": seconds
        }

        logger.info(
            f"Creating image-to-video job: image={filename} ({mime_type}, {width}x{height}), prompt='{prompt[:50]}...'")
        response = requests.post(
            url, headers=multipart_headers, data=data, files=files)

        if not response.ok:
            self._handle_api_error(response)

        sora_response = response.json()
        return convert_sora2_response_to_job_format(sora_response)

    def create_remix_job(self, video_id: str, prompt: str) -> dict:
        """
        Create a remix job to modify an existing video (video-to-video).

        Remix preserves the original video's framework, scene transitions, and layout
        while implementing the requested changes. For best results, limit modifications
        to one clearly articulated adjustment.

        Args:
            video_id (str): ID of the existing video to remix (e.g., "video_...").
            prompt (str): New prompt describing the desired modifications.

        Returns:
            dict: Remix job details with converted format.
        """
        # Remix uses a separate endpoint: /videos/remix
        url = f"{self.base_url}/remix"
        payload = {
            "model": self.deployment_name,
            "video_id": video_id,
            "prompt": prompt
        }

        logger.info(
            f"Creating remix job for video {video_id}: prompt='{prompt[:50]}...'")
        response = requests.post(url, json=payload, headers=self.headers)

        if not response.ok:
            self._handle_api_error(response)

        sora_response = response.json()
        return convert_sora2_response_to_job_format(sora_response)

    def get_video_generation_job(self, job_id: str) -> dict:
        """
        Retrieve the status of a video generation job.

        Args:
            job_id (str): The video/job ID.

        Returns:
            dict: Job status and details with converted format.
        """
        url = f"{self.base_url}/{job_id}"
        logger.info(f"Getting video generation job: {job_id}")
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        sora_response = response.json()
        return convert_sora2_response_to_job_format(sora_response)

    def delete_video_generation_job(self, job_id: str) -> int:
        """
        Delete a video generation job.

        Args:
            job_id (str): The video/job ID.

        Returns:
            int: HTTP status code (204 indicates success).
        """
        url = f"{self.base_url}/{job_id}"
        logger.info(f"Deleting video generation job: {job_id}")
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()
        return response.status_code

    def list_video_generation_jobs(self, before: str = None, after: str = None,
                                   limit: int = 10, statuses: list = None) -> dict:
        """
        List video generation jobs.

        Args:
            before (str, optional): Return jobs before this ID.
            after (str, optional): Return jobs after this ID.
            limit (int, optional): Maximum number of jobs to return.
            statuses (list, optional): Filter by status (e.g., ["queued", "completed"]).

        Returns:
            dict: Dictionary with "data" key containing list of jobs.
        """
        url = self.base_url
        params = {"limit": limit}
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        if statuses:
            params["statuses"] = ",".join(statuses)

        logger.info(f"Listing video generation jobs with params: {params}")
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()

        sora_response = response.json()
        videos = sora_response.get("data", sora_response) if isinstance(
            sora_response, dict) else sora_response
        if not isinstance(videos, list):
            videos = [videos]

        # Convert each video to expected format
        converted = [convert_sora2_response_to_job_format(
            video) for video in videos]
        return {"data": converted}

    def get_video_generation_video_content(self, generation_id: str, file_name: str,
                                           target_folder: str = 'videos') -> str:
        """
        Download the video content as an MP4 file.

        Args:
            generation_id (str): The video ID.
            file_name (str): The filename to save the video as (include .mp4 extension).
            target_folder (str): The folder to save the video to (default: 'videos').

        Returns:
            str: The path to the downloaded file.
        """
        url = f"{self.base_url}/{generation_id}/content"

        # Create directory if it doesn't exist
        os.makedirs(target_folder, exist_ok=True)
        file_path = os.path.join(target_folder, file_name)

        logger.info(f"Downloading video {generation_id} to {file_path}")
        response = requests.get(url, headers=self.headers, stream=True)
        response.raise_for_status()

        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Successfully downloaded video to {file_path}")
        return file_path

    def get_video_generation_video_stream(self, generation_id: str) -> io.BytesIO:
        """
        Retrieve video content as an in-memory bytes stream.

        Args:
            generation_id (str): The video ID.

        Returns:
            io.BytesIO: In-memory stream containing the video data.
        """
        url = f"{self.base_url}/{generation_id}/content"

        logger.info(f"Streaming video {generation_id}")
        response = requests.get(url, headers=self.headers, stream=True)
        response.raise_for_status()

        video_stream = io.BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                video_stream.write(chunk)
        video_stream.seek(0)
        return video_stream


class VideoExtractor:
    """Extract raw frames from a video together with precise timestamps (hh:mm:ss.mmm)."""

    def __init__(self, uri: str):
        self.uri = uri
        self.cap = cv2.VideoCapture(uri)
        if not self.cap.isOpened():
            raise ValueError("Error opening video file")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.frame_count / self.fps

    # Internal helpers
    def _grab_frame(self, frame_index: int) -> Dict[str, str]:
        """Return a single frame (JPEG-base64) and its timestamp string."""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        if not ret:
            return {}

        # Compute timestamp string
        timestamp_sec = frame_index / self.fps
        minutes = int(timestamp_sec // 60)
        seconds = int(timestamp_sec % 60)
        milliseconds = int((timestamp_sec - int(timestamp_sec)) * 1000)
        timestamp = f"{minutes:02}:{seconds:02}:{milliseconds:03}"

        # Encode JPEG → base64
        _, buffer = cv2.imencode(".jpg", frame)
        return {
            "timestamp": timestamp,
            "frame_base64": base64.b64encode(buffer).decode("utf-8"),
        }

    # Public API
    def extract_video_frames(self, interval: float) -> List[Dict[str, str]]:
        """Extract frames every *interval* seconds (no visual overlay)."""
        frame_indices = (np.arange(0, self.duration, interval)
                         * self.fps).astype(int)
        return [f for idx in frame_indices if (f := self._grab_frame(idx))]

    def extract_n_video_frames(self, n: int) -> List[Dict[str, str]]:
        """Extract *n* equally spaced frames across the whole video."""
        if n <= 0:
            raise ValueError("n must be > 0")
        if n > self.frame_count:
            raise ValueError("n cannot exceed total frame count")

        frame_indices = (
            np.linspace(0, self.duration, n, endpoint=False) * self.fps
        ).astype(int)
        return [f for idx in frame_indices if (f := self._grab_frame(idx))]


class VideoAnalyzer:
    """Send frames with timestamps to an OpenAI multimodal chat model."""

    def __init__(self, openai_client, model: str):
        self.openai_client = openai_client
        self.model = model

    def video_chat(
        self,
        frames: List[Dict[str, str]],
        system_message: str,
        transcription_note: str = None,
        max_retries: int = 3,
        retry_delay: int = 2,
    ) -> dict:
        # Build multimodal content: [image, timestamp text, image, timestamp text, ..., note]
        content_segments = []
        for f in frames:
            content_segments.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpg;base64,{f['frame_base64']}",
                        "detail": "auto",
                    },
                }
            )
            content_segments.append(
                {"type": "text", "text": f"timestamp: {f['timestamp']}"})

        if transcription_note:
            content_segments.append(
                {"type": "text", "text": transcription_note})

        messages = [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": "These are the frames from the video, each followed by its timestamp.",
            },
            {"role": "user", "content": content_segments},
        ]

        for attempt in range(max_retries):
            if attempt:
                logger.info(
                    "Retrying VideoAnalyzer.video_chat() - attempt %s", attempt)
                time.sleep(retry_delay)

            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                seed=0,
                response_format={"type": "json_object"},
            )

            try:
                return json.loads(response.choices[0].message.content)
            except (json.JSONDecodeError, ValueError):
                logger.warning("Invalid JSON returned by LLM - retrying ...")

        raise RuntimeError(
            "Failed to obtain a valid JSON response from the model")


def get_video_metadata(video_path: str) -> dict:
    """
    Returns duration (s), fps, resolution (WxH), and bitrate (kbps) for a video file.

    Args:
        video_path (str): Path to the video file.

    Returns:
        dict: Dictionary with keys: duration, fps, resolution, bitrate_kbps.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"File not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Error opening video file.")

    # Get properties
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Duration in seconds
    duration = frame_count / fps if fps else 0

    # File size in bits
    file_size_bytes = os.path.getsize(video_path)
    file_size_bits = file_size_bytes * 8

    # Bitrate in kilobits per second (kbps)
    bitrate = (file_size_bits / duration) / 1000 if duration else 0

    cap.release()
    return {
        "duration": round(duration, 2),
        "fps": round(fps, 2),
        "resolution": f"{width}x{height}",
        "bitrate_kbps": round(bitrate, 2)
    }
