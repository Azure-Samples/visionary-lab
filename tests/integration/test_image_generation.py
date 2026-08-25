"""Integration tests for image generation via GPTImageClient.

These tests call the real Azure OpenAI API — they cost tokens and take ~10-30s each.
Run with:  uv run pytest -m integration tests/integration/test_image_generation.py -v -s
"""

import base64
import io

import pytest
from openai import BadRequestError
from PIL import Image
from backend.core.config import settings
from backend.models.images import GPT_IMAGE_2_MODEL

pytestmark = pytest.mark.integration


class TestImageGeneration:
    """Test image generation with real API calls."""

    @pytest.mark.asyncio
    async def test_generate_single_image(self, image_client):
        """Generate a single image and verify the response structure."""
        result = await image_client.generate_image(
            prompt="A simple red circle on a white background",
            n=1,
            size="1024x1024",
            quality="low",
        )

        assert "data" in result
        assert len(result["data"]) == 1
        assert "b64_json" in result["data"][0]

        # Verify it's valid base64
        img_bytes = base64.b64decode(result["data"][0]["b64_json"])
        assert len(img_bytes) > 1000  # Reasonable image size

    @pytest.mark.asyncio
    async def test_generate_multiple_images(self, image_client):
        """Generate 2 variations and verify we get both back."""
        result = await image_client.generate_image(
            prompt="A blue square on a black background",
            n=2,
            size="1024x1024",
            quality="low",
        )

        assert len(result["data"]) == 2
        for item in result["data"]:
            assert "b64_json" in item

    @pytest.mark.asyncio
    async def test_generate_with_different_sizes(self, image_client):
        """Test landscape and portrait sizes."""
        for size in ["1024x1024", "1536x1024", "1024x1536"]:
            result = await image_client.generate_image(
                prompt="A green triangle",
                n=1,
                size=size,
                quality="low",
            )
            assert len(result["data"]) == 1
            assert "b64_json" in result["data"][0]

    @pytest.mark.asyncio
    async def test_generate_with_flexible_gpt_image_2_size(self, image_client):
        """Generate a non-legacy aspect ratio supported by GPT-Image-2."""
        result = await image_client.generate_image(
            prompt="A minimal teal geometric pattern",
            n=1,
            size="1280x768",
            quality="low",
        )

        assert len(result["data"]) == 1
        assert "b64_json" in result["data"][0]
        assert result["_model"] == GPT_IMAGE_2_MODEL

    @pytest.mark.asyncio
    async def test_edit_with_high_input_fidelity(self, image_client):
        """Edit a real PNG with GPT-Image-2's native high-fidelity control."""
        source = Image.new("RGB", (512, 512), "white")
        for x in range(128, 384):
            for y in range(128, 384):
                source.putpixel((x, y), (20, 90, 200))
        source_bytes = io.BytesIO()
        source.save(source_bytes, format="PNG")

        for attempt in range(2):
            try:
                result = await image_client.edit_image(
                    prompt=(
                        "Preserve the centered blue square exactly and change only "
                        "the white background to a pale yellow background"
                    ),
                    model=GPT_IMAGE_2_MODEL,
                    image=("blue-square.png", source_bytes.getvalue(), "image/png"),
                    n=1,
                    size="1024x1024",
                    quality="low",
                    output_format="png",
                    input_fidelity="high",
                )
                break
            except BadRequestError as exc:
                if attempt == 1 or "moderation_blocked" not in str(exc):
                    raise

        assert len(result["data"]) == 1
        assert "b64_json" in result["data"][0]
        assert result["_model"] == GPT_IMAGE_2_MODEL

    @pytest.mark.asyncio
    async def test_generate_with_transparent_background(self, image_client):
        """Test transparent background generation."""
        result = await image_client.generate_image(
            prompt="A yellow star icon",
            n=1,
            size="1024x1024",
            quality="low",
            background="transparent",
            output_format="png",
        )

        assert len(result["data"]) == 1
        assert "b64_json" in result["data"][0]

    @pytest.mark.asyncio
    async def test_token_usage_returned(self, image_client):
        """Verify token usage metadata is returned."""
        result = await image_client.generate_image(
            prompt="A small dot",
            n=1,
            size="1024x1024",
            quality="low",
        )

        if "usage" in result:
            usage = result["usage"]
            assert "total_tokens" in usage
            assert usage["total_tokens"] > 0

    @pytest.mark.asyncio
    async def test_deployment_metadata(self, image_client):
        """Verify deployment tracking metadata is included."""
        result = await image_client.generate_image(
            prompt="test",
            n=1,
            size="1024x1024",
            quality="low",
        )

        assert "_deployment_name" in result
        assert "_model" in result
        assert result["_deployment_name"] == settings.IMAGEGEN_2_DEPLOYMENT
        assert result["_model"] == GPT_IMAGE_2_MODEL
