"""Integration tests for the image pipeline (generate → save → analyze).

These tests exercise the full pipeline with real Azure services.
Run with:  uv run pytest -m integration tests/integration/test_pipeline.py -v -s
"""

import base64
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.core.config import settings
from backend.models.images import GPT_IMAGE_2_MODEL

pytestmark = pytest.mark.integration


class TestImagePipeline:
    """Test the ImagePipelineService with real image generation but mocked storage."""

    @pytest.mark.asyncio
    async def test_generate_via_pipeline(self, image_settings):
        """Generate an image through the pipeline service."""
        from backend.core.image_pipeline import ImagePipelineService
        from backend.models.images import ImageGenerationRequest

        service = ImagePipelineService()

        request = ImageGenerationRequest(
            prompt="A simple blue circle on white background",
            model=GPT_IMAGE_2_MODEL,
            size="1024x1024",
            quality="low",
            n=1,
        )

        try:
            result = await service.generate(request)

            assert result is not None
            assert result.success is True
            assert result.imgen_model_response is not None
            assert "data" in result.imgen_model_response
            assert len(result.imgen_model_response["data"]) >= 1
        finally:
            await service.close()

    @pytest.mark.asyncio
    async def test_pipeline_save_to_storage(self, storage_settings):
        """Test saving a generated image to Azure Blob Storage."""
        from backend.core.image_pipeline import ImagePipelineService
        from backend.core.azure_storage import AzureBlobStorageService
        from backend.models.images import ImageSaveRequest, ImageGenerationResponse

        service = ImagePipelineService()
        storage = AzureBlobStorageService()

        # Create a minimal test image as base64
        from PIL import Image as PILImage
        import io

        img = PILImage.new("RGB", (64, 64), color=(0, 128, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")

        gen_response = ImageGenerationResponse(
            success=True,
            message="test",
            imgen_model_response={"data": [{"b64_json": b64_data}]},
        )

        request = ImageSaveRequest(
            generation_response=gen_response,
            output_format="png",
            folder_path="test-integration/",
        )

        result = None
        try:
            result = await service.save(
                request=request,
                azure_storage_service=storage,
            )

            assert result is not None
            assert result.total_saved >= 1
            if storage_settings["is_emulator"]:
                async with httpx.AsyncClient() as client:
                    response = await client.get(result.saved_images[0].url)
                assert response.status_code == 200
                assert response.headers["content-type"] == "image/png"
                assert response.content.startswith(b"\x89PNG")
        finally:
            if result is not None:
                for saved in result.saved_images:
                    storage.delete_asset(
                        saved.blob_name,
                        settings.AZURE_BLOB_IMAGE_CONTAINER,
                    )
            await storage.close()

    @pytest.mark.asyncio
    async def test_full_generate_and_analyze(self, image_client, llm_client, async_llm_client):
        """Generate an image, then analyze it — full round trip."""
        from backend.core.analyze import ImageAnalyzer
        from backend.core.instructions import analyze_image_system_message

        # Step 1: Generate
        gen_result = await image_client.generate_image(
            prompt="A bright yellow sunflower in a field",
            n=1,
            size="1024x1024",
            quality="low",
        )

        assert len(gen_result["data"]) == 1
        image_b64 = gen_result["data"][0]["b64_json"]

        # Step 2: Analyze
        analyzer = ImageAnalyzer(
            openai_client=llm_client,
            model=settings.LLM_DEPLOYMENT,
            async_openai_client=async_llm_client,
        )

        analysis = await analyzer.async_image_chat(
            image_base64=image_b64,
            system_message=analyze_image_system_message,
        )

        assert isinstance(analysis, dict)
        assert "description" in analysis
        assert "tags" in analysis
        # The analysis should mention something related to the image
        desc_lower = analysis["description"].lower()
        assert any(word in desc_lower for word in ["sunflower", "yellow", "flower", "field"])
