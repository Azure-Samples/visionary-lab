"""Integration tests for video generation via Sora client.

These tests call the real Azure Sora 2 API — video jobs are async and may take minutes.
Run with:  uv run pytest tests/integration/test_video_generation.py -v -s
"""

import asyncio
import pytest

pytestmark = pytest.mark.integration


class TestVideoGeneration:
    """Test video generation with real Sora 2 API calls."""

    @pytest.mark.asyncio
    async def test_create_video_job(self, sora_client):
        """Create a video generation job and verify the job response."""
        result = await sora_client.create_video_generation_job(
            prompt="A calm ocean wave gently rolling onto a sandy beach at sunset",
            n_seconds=4,
            height=720,
            width=1280,
        )

        assert result is not None
        assert "id" in result
        assert result["id"]  # Non-empty job ID
        assert result.get("status") in ("queued", "in_progress", "running")

    @pytest.mark.asyncio
    async def test_list_video_jobs(self, sora_client):
        """List existing video generation jobs."""
        result = await sora_client.list_video_generation_jobs()

        assert result is not None
        # Should be a list (may be empty if no prior jobs)
        assert isinstance(result, (list, dict))

    @pytest.mark.asyncio
    async def test_create_and_poll_video_job(self, sora_client):
        """Create a job and poll for status update (don't wait for completion)."""
        job = await sora_client.create_video_generation_job(
            prompt="A red balloon floating upward against a clear blue sky",
            n_seconds=4,
            height=720,
            width=1280,
        )

        job_id = job["id"]
        assert job_id

        # Poll once to verify we can retrieve the job
        status = await sora_client.get_video_generation_job(job_id)
        assert status is not None
        assert "id" in status
        assert status["id"] == job_id
        assert "status" in status

    @pytest.mark.asyncio
    async def test_video_size_validation(self, sora_client):
        """Verify that invalid sizes are rejected."""
        with pytest.raises(ValueError, match="Unsupported video size"):
            await sora_client.create_video_generation_job(
                prompt="test",
                n_seconds=4,
                height=999,
                width=999,
            )

    @pytest.mark.asyncio
    async def test_portrait_video(self, sora_client):
        """Create a portrait-orientation video job."""
        result = await sora_client.create_video_generation_job(
            prompt="A single candle flame flickering in darkness",
            n_seconds=4,
            height=1280,
            width=720,
        )

        assert result is not None
        assert "id" in result
