from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any, Union, Literal
from enum import Enum
from backend.models.common import BaseResponse
from pydantic import validator

# TODO: Implement full image models with all required parameters and fields


class ImagePromptEnhancementRequest(BaseModel):
    """Request model for enhancing image generation prompts"""
    original_prompt: str = Field(...,
                                 description="Prompt to enhance for image generation")


class ImagePromptEnhancementResponse(BaseModel):
    """Response model for enhanced image generation prompts"""
    enhanced_prompt: str = Field(...,
                                 description="Enhanced prompt for image generation")


class ImagePromptBrandProtectionRequest(BaseModel):
    """Request model for enhancing image generation prompts"""
    original_prompt: str = Field(...,
                                 description="Prompt to protect for image generation")
    brands_to_protect: Optional[str] = Field(None,
                                             description="Str or comma-separated brands to protect in the prompt.")
    protection_mode: Optional[str] = Field("neutralize",
                                           description="Mode for brand protection: 'neutralize' (default) or 'replace'. Neutralize removes the brand, while replace substitutes competitirs with the protected brand.")


class ImagePromptBrandProtectionResponse(BaseModel):
    """Response model for rewritten image generation prompts"""
    enhanced_prompt: str = Field(...,
                                 # Using OpenAI DALL-E as placeholder for gpt-image-1 because of API similarity
                                 description="Rewritten prompt for image generation")


class ImageGenerationRequest(BaseModel):
    """Request model for image generation"""

    # common parameters for gpt-image-1:
    prompt: str = Field(...,
                        description="User prompt for image generation. Maximum 32000 characters for gpt-image-1.",
                        examples=["A futuristic city skyline at sunset"])
    model: str = Field("gpt-image-1",
                       description="Image generation model to use",
                       examples=["gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"])
    
    @validator('model')
    def validate_model(cls, v):
        """Validate that the model is one of the supported models"""
        valid_models = ["gpt-image-1", "gpt-image-1.5", "gpt-image-1-mini"]
        if v not in valid_models:
            raise ValueError(f"Model must be one of {valid_models}")
        return v
    n: int = Field(1,
                   description="Number of images to generate (1-10)")
    size: str = Field("auto",
                      description="Output image dimensions. Must be one of 1024x1024, 1536x1024 (landscape), 1024x1536 (portrait), or auto.",
                      examples=["1024x1024", "1536x1024", "1024x1536", "auto"])
    response_format: str = Field("b64_json",
                                 description="Response format for the generated image. Note: gpt-image-1 always returns b64_json regardless of this setting.",
                                 examples=["b64_json"])
    # gpt-image-1 specific parameters:
    quality: Optional[str] = Field("auto",
                                   description="Quality setting: 'low', 'medium', 'high', 'auto'. Defaults to auto.",
                                   examples=["low", "medium", "high", "auto"])
    output_format: Optional[str] = Field("png",
                                         description="Output format: 'png', 'webp', 'jpeg'. Defaults to png.",
                                         examples=["png", "webp", "jpeg"])
    output_compression: Optional[int] = Field(100,
                                              description="Compression rate percentage for WEBP and JPEG (0-100). Only valid with webp or jpeg output formats.")
    background: Optional[str] = Field("auto",
                                      description="Background setting: 'transparent', 'opaque', 'auto'. For transparent, output_format should be png or webp.",
                                      examples=["transparent", "opaque", "auto"])
    moderation: Optional[str] = Field("auto",
                                      description="Moderation strictness: 'auto', 'low'. Controls content filtering level.",
                                      examples=["auto", "low"])
    user: Optional[str] = Field(None,
                                description="A unique identifier representing your end-user, which helps OpenAI monitor and detect abuse.")


class ImageEditRequest(ImageGenerationRequest):
    """Request model for image editing"""

    image: Union[str, HttpUrl, List[Union[str, HttpUrl]]] = Field(...,
                                                                  description="The image(s) to edit. For gpt-image-1, you can provide up to 10 images, each should be a png, webp, or jpg file less than 25MB. Can be local file path(s), Base64-encoded image(s) (data URI) or URL(s).",
                                                                  examples=[
                                                                      "images/image.png",
                                                                      ["images/image1.png",
                                                                       "images/image2.png"],
                                                                      "https://example.com/image.png",
                                                                      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
                                                                  ])

    mask: Optional[Union[str, HttpUrl]] = Field(None,
                                                description="An additional image whose fully transparent areas indicate where the first image should be edited. Must be a valid PNG file with the same dimensions as the first image, and have an alpha channel.",
                                                examples=[
                                                    "images/mask.png",
                                                    "https://example.com/mask.png",
                                                    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
                                                ])

    # gpt-image-1 specific edit parameters:
    input_fidelity: Optional[str] = Field("low",
                                          description="Input fidelity setting for image editing: 'low' (default, faster), 'high' (better reproduction of input image features, additional cost). Only available for image editing operations.",
                                          examples=["low", "high"])

    @validator('input_fidelity')
    def validate_input_fidelity(cls, v):
        if v is not None and v not in ["low", "high"]:
            raise ValueError("input_fidelity must be either 'low' or 'high'")
        return v


class InputTokensDetails(BaseModel):
    """Details about input tokens for image generation"""
    text_tokens: int = Field(
        0, description="Number of text tokens in the input prompt")
    image_tokens: int = Field(
        0, description="Number of image tokens in the input")


class TokenUsage(BaseModel):
    """Token usage information for image generation"""
    total_tokens: int = Field(0, description="Total number of tokens used")
    input_tokens: int = Field(0, description="Number of tokens in the input")
    output_tokens: int = Field(
        0, description="Number of tokens in the output image(s)")
    input_tokens_details: Optional[InputTokensDetails] = Field(
        None, description="Detailed breakdown of input tokens")


class ImageGenerationResponse(BaseResponse):
    """Response model for image generation"""

    imgen_model_response: Optional[Dict[str, Any]] = Field(
        None, description="JSON response from the image generation API"
    )
    token_usage: Optional[TokenUsage] = Field(
        None, description="Token usage information (for gpt-image-1 only)"
    )


class ImageSaveRequest(BaseModel):
    """Request model for saving generated images to blob storage"""

    generation_response: ImageGenerationResponse = Field(
        ..., description="Response from the image generation API to save"
    )
    prompt: Optional[str] = Field(
        None, description="Original prompt used for generation (for metadata)"
    )
    model: Optional[str] = Field(
        None, description="Model used for generation (for metadata)"
    )
    size: Optional[str] = Field(
        None, description="Size used for generation (e.g., '1024x1024') (for metadata)"
    )
    background: Optional[str] = Field(
        "auto", description="Background setting: 'transparent', 'opaque', 'auto'. For transparent images."
    )
    output_format: Optional[str] = Field(
        "png", description="Output format: 'png', 'webp', 'jpeg'. Defaults to png."
    )
    save_all: bool = Field(
        True, description="Whether to save all generated images or just the first one"
    )
    folder_path: Optional[str] = Field(
        None, description="Folder path to save the images to (e.g., 'my-folder' or 'folder/subfolder')"
    )
    analyze: bool = Field(
        False, description="Whether to analyze images after saving and store analysis results"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata to persist alongside the saved image records",
    )


class ImageSaveResponse(BaseResponse):
    """Response model for saving generated images to blob storage"""

    saved_images: List[Dict[str, Any]] = Field(
        ..., description="List of saved image details from blob storage"
    )
    total_saved: int = Field(
        ..., description="Total number of images saved"
    )
    prompt: Optional[str] = Field(
        None, description="Original prompt used for generation"
    )
    analysis_results: Optional[List[Dict[str, Any]]] = Field(
        None, description="Analysis results for each image (if analyze=True)"
    )
    analyzed: bool = Field(
        False, description="Whether images were analyzed"
    )


class ImageGenerateWithAnalysisRequest(BaseModel):
    """Request model for generating, analyzing, and saving images in one call"""
    # Generation parameters (mirrors ImageGenerationRequest)
    prompt: str = Field(..., description="User prompt for image generation")
    model: str = Field("gpt-image-1", description="Image generation model to use")
    n: int = Field(1, description="Number of images to generate (1-10)")
    size: str = Field(
        "auto",
        description="Output image dimensions. One of 1024x1024, 1536x1024, 1024x1536, or auto.",
    )
    response_format: str = Field(
        "b64_json",
        description="Response format for generated image(s). gpt-image-1 returns b64_json",
    )
    quality: Optional[str] = Field(
        "auto", description="Quality setting: 'low', 'medium', 'high', 'auto'"
    )
    output_format: Optional[str] = Field(
        "png", description="Output format: 'png', 'webp', 'jpeg'"
    )
    output_compression: Optional[int] = Field(
        100,
        description="Compression percentage for WEBP/JPEG (0-100). Only for webp/jpeg",
    )
    background: Optional[str] = Field(
        "auto",
        description="Background: 'transparent', 'opaque', 'auto'. Transparent needs png/webp",
    )
    moderation: Optional[str] = Field(
        "auto", description="Moderation strictness: 'auto', 'low'"
    )
    user: Optional[str] = Field(
        None, description="End-user identifier for abuse monitoring"
    )

    # Save/analysis parameters
    save_all: bool = Field(True, description="Whether to save all variants or first only")
    folder_path: Optional[str] = Field(
        None, description="Folder path to save images (e.g., 'my-album' or 'a/b')"
    )
    analyze: bool = Field(
        True, description="Whether to analyze images and store analysis results"
    )


class ImageListRequest(BaseModel):
    """Request model for listing images"""
    # TODO: Add filtering and sorting parameters
    limit: int = Field(50, description="Number of images to return")
    offset: int = Field(0, description="Offset for pagination")


class ImageListResponse(BaseResponse):
    """Response model for listing images"""
    # TODO: Enhance with metadata and filtering info
    images: List[dict] = Field(..., description="List of images")
    total: int = Field(..., description="Total number of images")
    limit: int = Field(..., description="Number of images per page")
    offset: int = Field(..., description="Offset for pagination")


class ImageDeleteRequest(BaseModel):
    """Request model for deleting an image"""
    # TODO: Add options for bulk deletion
    image_id: str = Field(..., description="ID of the image to delete")


class ImageDeleteResponse(BaseResponse):
    """Response model for image deletion"""
    # TODO: Add more detailed status information
    image_id: str = Field(..., description="ID of the deleted image")


class ImageAnalyzeRequest(BaseModel):
    """Request model for analyzing an image"""
    image_path: Optional[str] = Field(
        None,
        description="Path to the image file on Azure Blob Storage. Supports a full URL with or without a SAS token."
    )
    base64_image: Optional[str] = Field(
        None,
        description="Base64-encoded image data to analyze directly. Must not include the 'data:image/...' prefix."
    )

    @validator('image_path', 'base64_image')
    def validate_at_least_one_source(cls, v, values):
        # If we're validating base64_image and image_path was empty, base64_image must not be None
        # Or if we're validating image_path and base64_image is not in values, image_path must not be None
        if 'image_path' in values and values['image_path'] is None and v is None:
            raise ValueError(
                "Either image_path or base64_image must be provided")
        return v


class ImageAnalyzeCustomRequest(BaseModel):
    """Request model for analyzing an image with a custom prompt"""
    image_path: Optional[str] = Field(
        None,
        description="Path to the image file on Azure Blob Storage. Supports a full URL with or without a SAS token."
    )
    base64_image: Optional[str] = Field(
        None,
        description="Base64-encoded image data to analyze directly. Must not include the 'data:image/...' prefix."
    )
    custom_prompt: str = Field(
        ...,
        description="Custom instructions for analyzing the image. This will guide what aspects the AI should focus on."
    )

    @validator('image_path', 'base64_image')
    def validate_at_least_one_source(cls, v, values):
        # If we're validating base64_image and image_path was empty, base64_image must not be None
        # Or if we're validating image_path and base64_image is not in values, image_path must not be None
        if 'image_path' in values and values['image_path'] is None and v is None:
            raise ValueError(
                "Either image_path or base64_image must be provided")
        return v


class ImageAnalyzeResponse(BaseModel):
    """Response model for image analysis results"""
    description: str = Field(..., description="Description of the content")
    products: str = Field(..., description="Products identified in the image")
    tags: List[str] = Field(...,
                            description="List of metadata tags for the image")
    feedback: str = Field(...,
                          description="Feedback on the image quality/content")


class ImageFilenameGenerateRequest(BaseModel):
    """Request model for generating a filename based on content"""
    prompt: str = Field(...,
                        description="Prompt describing the content to name")
    extension: Optional[str] = Field(
        None, description="File extension for the generated filename, e.g., .png, .jpg, .webp"
    )


class ImageFilenameGenerateResponse(BaseModel):
    """Response model for filename generation"""
    filename: str = Field(..., description="Generated filename")


class PipelineAction(str, Enum):
    """Supported primary operations for the image pipeline."""

    GENERATE = "generate"
    EDIT = "edit"


class PipelineSaveOptions(BaseModel):
    """Configuration for the optional persistence stage."""

    enabled: bool = Field(False, description="Persist generated assets when true")
    save_all: bool = Field(True, description="Persist every variant instead of the first")
    folder_path: Optional[str] = Field(
        None, description="Virtual folder path to store saved assets"
    )
    output_format: Optional[str] = Field(
        None, description="Override output format at save time"
    )
    background: Optional[str] = Field(
        None, description="Override background metadata for saved images"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata merged into Cosmos DB records"
    )


class PipelineAnalysisOptions(BaseModel):
    """Configuration for downstream analysis."""

    enabled: bool = Field(False, description="Run analysis after generation/save")
    custom_prompt: Optional[str] = Field(
        None,
        description="Optional override for the analysis system instructions",
    )


class ImagePipelineRequest(BaseModel):
    """Unified payload driving the image pipeline."""

    action: PipelineAction = Field(
        PipelineAction.GENERATE,
        description="Primary pipeline action to execute",
    )
    prompt: str = Field(..., description="Prompt used for generation or editing")
    model: str = Field(
        "gpt-image-1", description="Model deployment identifier"
    )
    n: int = Field(1, description="Number of variants to produce (1-10)")
    size: str = Field(
        "auto",
        description="Requested output size (1024x1024, 1536x1024, 1024x1536, or auto)",
    )
    response_format: str = Field(
        "b64_json", description="Expected response format from the model"
    )
    quality: Optional[str] = Field(
        "auto", description="Quality hint for gpt-image-1"
    )
    output_format: Optional[str] = Field(
        "png", description="Desired output format"
    )
    output_compression: Optional[int] = Field(
        100,
        description="Compression percentage for webp/jpeg outputs (0-100)",
    )
    background: Optional[str] = Field(
        "auto", description="Background handling (transparent, opaque, auto)"
    )
    moderation: Optional[str] = Field(
        "auto", description="Moderation strictness passed to the model"
    )
    user: Optional[str] = Field(
        None, description="End-user identifier forwarded to the provider"
    )
    input_fidelity: Optional[str] = Field(
        "low", description="Input fidelity used for edit operations ('low' or 'high')"
    )
    source_image_urls: Optional[List[HttpUrl]] = Field(
        None,
        description="Existing image URLs to edit when uploads are not provided",
    )
    source_image_base64: Optional[List[str]] = Field(
        None,
        description="Base64 encoded source images (without the data URL prefix)",
    )
    mask_image_url: Optional[HttpUrl] = Field(
        None, description="Optional mask image URL for edit operations"
    )
    save_options: PipelineSaveOptions = Field(
        default_factory=PipelineSaveOptions,
        description="Save configuration",
    )
    analysis_options: PipelineAnalysisOptions = Field(
        default_factory=PipelineAnalysisOptions,
        description="Analysis configuration",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Arbitrary metadata forwarded through the pipeline"
    )


class PipelineStepResult(BaseModel):
    """Describes the outcome of a single pipeline stage."""

    step: Literal["generate", "edit", "save", "analyze"]
    success: bool
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ImagePipelineResponse(BaseResponse):
    """Aggregated response returned by the unified pipeline endpoint."""

    steps: List[PipelineStepResult] = Field(
        ..., description="Ordered pipeline step summaries"
    )
    generation: Optional[ImageGenerationResponse] = Field(
        None, description="Generation/edit stage response payload"
    )
    save: Optional[ImageSaveResponse] = Field(
        None, description="Save stage response when executed"
    )
