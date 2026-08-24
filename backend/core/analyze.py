import asyncio
import json
import logging
import time

logger = logging.getLogger(__name__)

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
