"""Integration tests for image and video analysis via LLM.

These tests call the real Azure OpenAI LLM API.
Run with:  uv run pytest tests/integration/test_analysis.py -v -s
"""

import base64
import pytest
from backend.core.analyze import ImageAnalyzer, VideoAnalyzer
from backend.core.config import settings
from backend.core.instructions import (
    analyze_image_system_message,
    analyze_video_system_message,
    img_prompt_enhance_msg,
)

pytestmark = pytest.mark.integration


def _create_test_image_b64() -> str:
    """Create a minimal 8x8 red PNG and return as base64."""
    from PIL import Image
    import io

    img = Image.new("RGB", (8, 8), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class TestImageAnalysis:
    """Test image analysis with real LLM calls."""

    def test_sync_image_analysis(self, llm_client):
        """Analyze a test image synchronously and verify JSON structure."""
        analyzer = ImageAnalyzer(
            openai_client=llm_client,
            model=settings.LLM_DEPLOYMENT,
        )

        image_b64 = _create_test_image_b64()
        result = analyzer.image_chat(
            image_base64=image_b64,
            system_message=analyze_image_system_message,
        )

        assert isinstance(result, dict)
        assert "description" in result
        assert "tags" in result
        assert isinstance(result["tags"], list)
        assert len(result["tags"]) > 0

    @pytest.mark.asyncio
    async def test_async_image_analysis(self, llm_client, async_llm_client):
        """Analyze a test image asynchronously."""
        analyzer = ImageAnalyzer(
            openai_client=llm_client,
            model=settings.LLM_DEPLOYMENT,
            async_openai_client=async_llm_client,
        )

        image_b64 = _create_test_image_b64()
        result = await analyzer.async_image_chat(
            image_base64=image_b64,
            system_message=analyze_image_system_message,
        )

        assert isinstance(result, dict)
        assert "description" in result
        assert "tags" in result


class TestPromptEnhancement:
    """Test prompt enhancement with real LLM calls."""

    def test_enhance_image_prompt(self, llm_client):
        """Enhance a simple prompt and verify the result is richer."""
        import json

        response = llm_client.chat.completions.create(
            model=settings.LLM_DEPLOYMENT,
            messages=[
                {"role": "system", "content": img_prompt_enhance_msg},
                {"role": "user", "content": "a dog in a park"},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        assert "prompt" in result
        enhanced = result["prompt"]
        assert len(enhanced) > len("a dog in a park")
        assert isinstance(enhanced, str)

    def test_enhance_video_prompt(self, llm_client):
        """Enhance a video prompt."""
        import json
        from backend.core.instructions import video_prompt_enhancement_system_message

        response = llm_client.chat.completions.create(
            model=settings.LLM_DEPLOYMENT,
            messages=[
                {"role": "system", "content": video_prompt_enhancement_system_message},
                {"role": "user", "content": "sunset on a beach"},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        assert "prompt" in result
        assert len(result["prompt"]) > len("sunset on a beach")
