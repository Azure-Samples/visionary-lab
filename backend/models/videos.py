from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union

# Models used by video API endpoints (Sora 2)


class VideoPromptEnhancementRequest(BaseModel):
    """Request model for enhancing video generation prompts"""
    original_prompt: str = Field(...,
                                 description="Prompt to enhance for video generation")


class VideoPromptEnhancementResponse(BaseModel):
    """Response model for enhanced video generation prompts"""
    enhanced_prompt: str = Field(...,
                                 description="Enhanced prompt for video generation")


class AudioGenerationSettings(BaseModel):
    """Audio generation settings for Sora 2"""
    enabled: bool = Field(True, description="Enable audio generation")
    language: Optional[str] = Field(None, description="Language for audio (e.g., 'en', 'es', 'fr')")
    include_speech: bool = Field(True, description="Include speech/dialogue in audio")
    include_sound_effects: bool = Field(True, description="Include ambient sounds and effects")
    voice_style: Optional[str] = Field(None, description="Voice style for speech (e.g., 'casual', 'professional')")


class CameoReference(BaseModel):
    """Cameo reference for personalized video generation"""
    id: str = Field(..., description="Unique ID of the cameo reference")
    created_at: Optional[int] = Field(None, description="Unix timestamp of creation")
    status: Optional[str] = Field(None, description="Status of cameo verification")


class CameoUploadRequest(BaseModel):
    """Request model for uploading cameo data"""
    face_image: str = Field(..., description="Base64 encoded face image")
    voice_audio: Optional[str] = Field(None, description="Base64 encoded voice audio sample")


class RemixVideoRequest(BaseModel):
    """Request model for remixing an existing video (video-to-video)"""
    video_id: str = Field(..., description="ID of the video to remix")
    prompt: str = Field(..., description="New prompt or modification instructions")
    style_transfer: Optional[str] = Field(None, description="Apply specific style transfer")
    face_swap: Optional[str] = Field(None, description="Cameo ID for face swapping")
    audio_override: Optional[AudioGenerationSettings] = Field(None, description="Override audio settings")


class VideoGenerationRequest(BaseModel):
    """Request model for generating videos using Sora 2"""
    prompt: str = Field(...,
                        description="Prompt describing the video to generate")
    n_seconds: int = Field(10, description="Length of the video in seconds (5, 10, 15, or 20)")
    height: int = Field(720, description="Height of the video in pixels")
    width: int = Field(1280, description="Width of the video in pixels")
    has_source_images: Optional[bool] = Field(
        False, description="Whether source images are included")
    image_count: Optional[int] = Field(
        None, description="Number of source images")
    audio: Optional[Union[bool, AudioGenerationSettings]] = Field(
        None, description="Audio generation settings (True for default, or detailed settings)")
    cameo: Optional[str] = Field(
        None, description="Cameo reference ID for personalized videos")
    remix_video_id: Optional[str] = Field(
        None, description="ID of existing video to remix")


class VideoGenerationJobResponse(BaseModel):
    """Response model for a video generation job (Sora 2)"""
    id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Current status of the job")
    prompt: str = Field(..., description="Original prompt used for generation")
    n_seconds: int = Field(..., description="Length of the video in seconds")
    height: int = Field(..., description="Height of the video in pixels")
    width: int = Field(..., description="Width of the video in pixels")
    generations: Optional[list] = Field(
        None, description="List of generated videos")
    created_at: Optional[int] = Field(
        None, description="Unix timestamp of creation time")
    finished_at: Optional[int] = Field(
        None, description="Unix timestamp of completion time")
    failure_reason: Optional[str] = Field(
        None, description="Reason for failure if job failed")
    has_audio: Optional[bool] = Field(
        None, description="Whether the video includes generated audio")
    cameo_used: Optional[str] = Field(
        None, description="Cameo reference ID if used")
    is_remix: Optional[bool] = Field(
        None, description="Whether this is a remix job")


class VideoAnalyzeRequest(BaseModel):
    """Request model for analyzing video content"""
    video_path: str = Field(...,
                            description="Path to the video file on Azure Blob Storage. Supports a full URL with or without a SAS token.")


class VideoAnalyzeResponse(BaseModel):
    """Response model for video analysis results"""
    summary: str = Field(..., description="Summary of the video content")
    products: str = Field(..., description="Products identified in the video")
    tags: List[str] = Field(...,
                            description="List of metadata tags for the video")
    feedback: str = Field(...,
                          description="Feedback on the video quality/content")


class VideoFilenameGenerateRequest(BaseModel):
    """Request model for generating a filename based on content"""
    prompt: str = Field(...,
                        description="Prompt describing the content to name")
    gen_id: Optional[str] = Field(
        None, description="Video generation id for unique naming"
    )
    extension: Optional[str] = Field(
        None, description="File extension for the generated filename, e.g., .mp4"
    )


class VideoFilenameGenerateResponse(BaseModel):
    """Response model for filename generation"""
    filename: str = Field(..., description="Generated filename")


class VideoGenerationWithAnalysisRequest(BaseModel):
    """Request model for generating videos with optional analysis"""
    prompt: str = Field(...,
                        description="Prompt describing the video to generate")
    n_seconds: int = Field(10, description="Length of the video in seconds")
    height: int = Field(720, description="Height of the video in pixels")
    width: int = Field(1280, description="Width of the video in pixels")
    analyze_video: bool = Field(
        False, description="Whether to analyze the generated videos")
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional metadata for the job")


class VideoGenerationWithAnalysisResponse(BaseModel):
    """Response model for video generation with analysis"""
    job: VideoGenerationJobResponse = Field(...,
                                            description="Video generation job details")
    analysis_results: Optional[List[VideoAnalyzeResponse]] = Field(
        None, description="Analysis results for each generated video (if analysis was requested)")
    upload_results: Optional[List[Dict[str, str]]] = Field(
        None, description="Upload results for each video to gallery")
