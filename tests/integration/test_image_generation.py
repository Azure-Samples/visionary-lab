"""Integration tests for image generation via GPTImageClient.

These tests call the real Azure OpenAI API — they cost tokens and take ~10-30s each.
Run with:  uv run pytest tests/integration/test_image_generation.py -v -s
"""

import base64
import pytest
from backend.core.config import settings

pytestmark = pytest.mark.integration


class TestImageGeneration:
    """Test image generation with real API calls."""

    def test_generate_single_image(self, image_client):
        """Generate a single image and verify the response structure."""
        result = image_client.generate_image(
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

    def test_generate_multiple_images(self, image_client):
        """Generate 2 variations and verify we get both back."""
        result = image_client.generate_image(
            prompt="A blue square on a black background",
            n=2,
            size="1024x1024",
            quality="low",
        )

        assert len(result["data"]) == 2
        for item in result["data"]:
            assert "b64_json" in item

    def test_generate_with_different_sizes(self, image_client):
        """Test landscape and portrait sizes."""
        for size in ["1024x1024", "1536x1024", "1024x1536"]:
            result = image_client.generate_image(
                prompt="A green triangle",
                n=1,
                size=size,
                quality="low",
            )
            assert len(result["data"]) == 1
            assert "b64_json" in result["data"][0]

    def test_generate_with_transparent_background(self, image_client):
        """Test transparent background generation."""
        result = image_client.generate_image(
            prompt="A yellow star icon",
            n=1,
            size="1024x1024",
            quality="low",
            background="transparent",
            output_format="png",
        )

        assert len(result["data"]) == 1
        assert "b64_json" in result["data"][0]

    def test_token_usage_returned(self, image_client):
        """Verify token usage metadata is returned."""
        result = image_client.generate_image(
            prompt="A small dot",
            n=1,
            size="1024x1024",
            quality="low",
        )

        if "usage" in result:
            usage = result["usage"]
            assert "total_tokens" in usage
            assert usage["total_tokens"] > 0

    def test_deployment_metadata(self, image_client):
        """Verify deployment tracking metadata is included."""
        result = image_client.generate_image(
            prompt="test",
            n=1,
            size="1024x1024",
            quality="low",
        )

        assert "_deployment_name" in result
        assert "_model" in result
        assert result["_deployment_name"] == settings.IMAGEGEN_DEPLOYMENT
