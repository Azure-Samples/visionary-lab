import asyncio
import base64
import json
import logging
import time
from typing import List, Dict, Optional

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        frame_indices = (np.arange(0, self.duration, interval) * self.fps).astype(int)
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

    def __init__(self, openai_client, model: str, async_openai_client=None):
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
        self.model = model

    async def async_video_chat(
        self,
        frames: List[Dict[str, str]],
        system_message: str,
        transcription_note: str = None,
        max_retries: int = 3,
        retry_delay: int = 2,
    ) -> dict:
        """Async version of video_chat for non-blocking LLM calls."""
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
            content_segments.append({"type": "text", "text": f"timestamp: {f['timestamp']}"})

        if transcription_note:
            content_segments.append({"type": "text", "text": transcription_note})

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
                logger.info("Retrying VideoAnalyzer.async_video_chat() - attempt %s", attempt)
                await asyncio.sleep(retry_delay)

            response = await self.async_openai_client.chat.completions.create(
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

        raise RuntimeError("Failed to obtain a valid JSON response from the model")

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
            content_segments.append({"type": "text", "text": f"timestamp: {f['timestamp']}"})

        if transcription_note:
            content_segments.append({"type": "text", "text": transcription_note})

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
                logger.info("Retrying VideoAnalyzer.video_chat() - attempt %s", attempt)
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

        raise RuntimeError("Failed to obtain a valid JSON response from the model")

class ImageAnalyzer:
    """Send a single image to an OpenAI multimodal chat model."""

    def __init__(self, openai_client, model: str, async_openai_client=None):
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
        self.model = model

    async def async_image_chat(
        self,
        image_base64: str,
        system_message: str,
        max_retries: int = 3,
        retry_delay: int = 2,
    ) -> dict:
        """
        Async version of image_chat for non-blocking LLM calls.

        Args:
            image_base64: Base64 encoded image data
            system_message: Instructions for the model
            max_retries: Number of attempts for successful API response
            retry_delay: Seconds to wait between retries

        Returns:
            Parsed JSON response from the model
        """
        messages = [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpg;base64,{image_base64}",
                            "detail": "auto",
                        },
                    }
                ],
            },
        ]

        for attempt in range(max_retries):
            if attempt:
                logger.info("Retrying ImageAnalyzer.async_image_chat() - attempt %s", attempt)
                await asyncio.sleep(retry_delay)

            response = await self.async_openai_client.chat.completions.create(
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

        raise RuntimeError("Failed to obtain a valid JSON response from the model")

    def image_chat(
        self,
        image_base64: str,
        system_message: str,
        max_retries: int = 3,
        retry_delay: int = 2,
    ) -> dict:
        """
        Process a single image with the LLM.
        
        Args:
            image_base64: Base64 encoded image data
            system_message: Instructions for the model
            max_retries: Number of attempts for successful API response
            retry_delay: Seconds to wait between retries
            
        Returns:
            Parsed JSON response from the model
        """
        messages = [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpg;base64,{image_base64}",
                            "detail": "auto",
                        },
                    }
                ],
            },
        ]

        for attempt in range(max_retries):
            if attempt:
                logger.info("Retrying ImageAnalyzer.image_chat() - attempt %s", attempt)
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

        raise RuntimeError("Failed to obtain a valid JSON response from the model")

