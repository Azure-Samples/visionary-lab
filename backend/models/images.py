import re

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from typing import List, Optional, Dict, Any, Union, Literal
from enum import Enum
from backend.models.common import BaseResponse
from pydantic import model_validator, validator

# TODO: Implement full image models with all required parameters and fields

GPT_IMAGE_2_MODEL = "gpt-image-2"
FLUX_KONTEXT_PRO_MODEL = "flux-kontext-pro"
SUPPORTED_IMAGE_MODELS = (GPT_IMAGE_2_MODEL, FLUX_KONTEXT_PRO_MODEL)

GPT_IMAGE_2_MIN_PIXELS = 655_360
GPT_IMAGE_2_MAX_PIXELS = 8_294_400
GPT_IMAGE_2_MAX_EDGE = 3_840
GPT_IMAGE_2_MAX_ASPECT_RATIO = 3
_IMAGE_SIZE_PATTERN = re.compile(r"^(?P<width>[1-9]\d*)x(?P<height>[1-9]\d*)$")


def validate_image_model(model: str) -> None:
    """Reject model identifiers that are not exposed by the application."""
    if model not in SUPPORTED_IMAGE_MODELS:
        raise ValueError(f"Model must be one of {list(SUPPORTED_IMAGE_MODELS)}")


def validate_image_size(model: str, size: str) -> None:
    """Validate the flexible GPT-Image-2 dimensions documented by Azure."""
    if model != GPT_IMAGE_2_MODEL or size == "auto":
        return

    match = _IMAGE_SIZE_PATTERN.fullmatch(size)
    if not match:
        raise ValueError("GPT-Image-2 size must be 'auto' or WIDTHxHEIGHT")

    width = int(match.group("width"))
    height = int(match.group("height"))
    if width % 16 or height % 16:
        raise ValueError("GPT-Image-2 width and height must be multiples of 16")
    if max(width, height) > GPT_IMAGE_2_MAX_EDGE:
        raise ValueError(
            f"GPT-Image-2 long edge must not exceed {GPT_IMAGE_2_MAX_EDGE} pixels"
        )
    if max(width, height) > GPT_IMAGE_2_MAX_ASPECT_RATIO * min(width, height):
        raise ValueError("GPT-Image-2 aspect ratio must be between 1:3 and 3:1")

    pixels = width * height
    if not GPT_IMAGE_2_MIN_PIXELS <= pixels <= GPT_IMAGE_2_MAX_PIXELS:
        raise ValueError(
            "GPT-Image-2 total pixels must be between "
            f"{GPT_IMAGE_2_MIN_PIXELS:,} and {GPT_IMAGE_2_MAX_PIXELS:,}"
        )


def validate_image_options(
    model: str,
    *,
    quality: Optional[str],
    output_format: Optional[str],
    response_format: str,
    background: Optional[str],
) -> None:
    """Validate GPT-Image-2 output controls shared across providers."""
    if model != GPT_IMAGE_2_MODEL:
        return
    if quality not in {"auto", "low", "medium", "high"}:
        raise ValueError("GPT-Image-2 quality must be auto, low, medium, or high")
    if output_format not in {"png", "jpeg", "webp"}:
        raise ValueError("GPT-Image-2 output_format must be png, jpeg, or webp")
    if response_format != "b64_json":
        raise ValueError("GPT-Image-2 response_format must be b64_json")
    if background not in {"auto", "transparent", "opaque"}:
        raise ValueError("GPT-Image-2 background must be auto, transparent, or opaque")
    if background == "transparent" and output_format not in {"png", "webp"}:
        raise ValueError(
            "GPT-Image-2 transparent backgrounds require png or webp output"
        )


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
                                 description="Rewritten prompt for image generation")


class ImageGenerationRequest(BaseModel):
    """Request model for image generation"""

    # Common GPT-Image-2 generation parameters.
    prompt: str = Field(...,
                        max_length=32000,
                        description="User prompt for image generation. Maximum 32000 characters for GPT-Image-2.",
                        examples=["A futuristic city skyline at sunset"])
    model: str = Field(GPT_IMAGE_2_MODEL,
                       description="Image generation model to use",
                       examples=list(SUPPORTED_IMAGE_MODELS))
    n: int = Field(1,
                   ge=1,
                   le=10,
                   description="Number of images to generate (1-10)")
    size: str = Field("auto",
                      description="GPT-Image-2 dimensions: auto or WIDTHxHEIGHT, with both edges divisible by 16, a 1:3 to 3:1 aspect ratio, 655,360-8,294,400 total pixels, and a maximum 3,840-pixel long edge.",
                      examples=["1024x1024", "3840x2160", "1024x1536", "auto"])
    response_format: str = Field("b64_json",
                                 description="Response format for the generated image. GPT-Image-2 returns b64_json.",
                                 examples=["b64_json"])
    # GPT-Image-2 output controls.
    quality: Optional[str] = Field("high",
                                   description="Quality setting: 'auto', 'low', 'medium', or 'high'. Defaults to high.",
                                   examples=["auto", "low", "medium", "high"])
    output_format: Optional[str] = Field("png",
                                         description="GPT-Image-2 output format: 'png', 'jpeg', or 'webp'. Defaults to png. Azure availability can vary by API surface.",
                                         examples=["png", "jpeg", "webp"])
    output_compression: Optional[int] = Field(100,
                                              description="Compression rate percentage for WEBP and JPEG (0-100). Only valid with webp or jpeg output formats.")
    background: Optional[str] = Field("auto",
                                      description="Background setting: 'transparent', 'opaque', or 'auto'. Transparent output requires png or webp.",
                                      examples=["transparent", "opaque", "auto"])
    moderation: Optional[str] = Field("auto",
                                      description="Moderation strictness: 'auto', 'low'. Controls content filtering level.",
                                      examples=["auto", "low"])
    user: Optional[str] = Field(None,
                                description="A unique identifier representing your end-user, which helps OpenAI monitor and detect abuse.")

    @model_validator(mode="after")
    def validate_model_capabilities(self):
        validate_image_model(self.model)
        validate_image_size(self.model, self.size)
        validate_image_options(
            self.model,
            quality=self.quality,
            output_format=self.output_format,
            response_format=self.response_format,
            background=self.background,
        )
        return self


class ImageEditRequest(ImageGenerationRequest):
    """Request model for image editing"""

    image: Union[str, HttpUrl, List[Union[str, HttpUrl]]] = Field(...,
                                                                  description="The image(s) to edit. GPT-Image-2 accepts PNG, JPG, or WebP images smaller than 50MB. Sources can be local paths, Base64 data, or URLs.",
                                                                  examples=[
                                                                      "images/image.png",
                                                                      ["images/image1.png",
                                                                       "images/image2.png"],
                                                                      "https://example.com/image.png",
                                                                      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
                                                                  ])

    mask: Optional[Union[str, HttpUrl]] = Field(None,
                                                description="An additional PNG or WebP image whose fully transparent areas indicate where the first image should be edited. It should match the first image dimensions and include an alpha channel.",
                                                examples=[
                                                    "images/mask.png",
                                                    "https://example.com/mask.png",
                                                    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
                                                ])

    # GPT-Image-2 edit controls.
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
        None, description="Token usage information returned by the image model"
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


class SavedImageAsset(BaseModel):
    """Stable artifact contract shared by jobs and the frontend."""

    model_config = ConfigDict(extra="allow")

    blob_name: str
    url: str
    original_filename: Optional[str] = None
    original_index: Optional[int] = Field(default=None, ge=1, le=10)
    container: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = Field(default=None, ge=0)
    width: Optional[int] = Field(default=None, ge=0)
    height: Optional[int] = Field(default=None, ge=0)
    folder_path: Optional[str] = None


class ImageSaveResponse(BaseResponse):
    """Response model for saving generated images to blob storage"""

    saved_images: List[SavedImageAsset] = Field(
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
    model: str = Field(GPT_IMAGE_2_MODEL, description="Image generation model to use")
    n: int = Field(1, description="Number of images to generate (1-10)")
    size: str = Field(
        "auto",
        description="GPT-Image-2 dimensions in WIDTHxHEIGHT form, or auto.",
    )
    response_format: str = Field(
        "b64_json",
        description="Response format for generated image(s). GPT-Image-2 returns b64_json",
    )
    quality: Optional[str] = Field(
        "high", description="Quality setting: 'auto', 'low', 'medium', or 'high'"
    )
    output_format: Optional[str] = Field(
        "png", description="Output format: 'png', 'jpeg', or 'webp'"
    )
    output_compression: Optional[int] = Field(
        100,
        description="Compression percentage for WEBP/JPEG (0-100). Only for webp/jpeg",
    )
    background: Optional[str] = Field(
        "auto",
        description="Background: 'transparent', 'opaque', or 'auto'. Transparent requires png or webp",
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

    @model_validator(mode="after")
    def validate_model_capabilities(self):
        validate_image_model(self.model)
        validate_image_size(self.model, self.size)
        validate_image_options(
            self.model,
            quality=self.quality,
            output_format=self.output_format,
            response_format=self.response_format,
            background=self.background,
        )
        return self


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

    @model_validator(mode="after")
    def validate_at_least_one_source(self):
        if self.image_path is None and self.base64_image is None:
            raise ValueError("Either image_path or base64_image must be provided")
        return self


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

    @model_validator(mode="after")
    def validate_at_least_one_source(self):
        if self.image_path is None and self.base64_image is None:
            raise ValueError("Either image_path or base64_image must be provided")
        return self


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
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="Prompt used for generation or editing",
    )
    model: str = Field(
        GPT_IMAGE_2_MODEL, description="Model deployment identifier"
    )
    n: int = Field(1, ge=1, le=10, description="Number of variants to produce (1-10)")
    size: str = Field(
        "auto",
        description="GPT-Image-2 dimensions in WIDTHxHEIGHT form, or auto",
    )
    response_format: str = Field(
        "b64_json", description="Expected response format from the model"
    )
    quality: Optional[str] = Field(
        "high", description="Quality hint for GPT-Image-2"
    )
    output_format: Optional[str] = Field(
        "png", description="Desired output format"
    )
    output_compression: Optional[int] = Field(
        100,
        ge=0,
        le=100,
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

    @model_validator(mode="after")
    def validate_model_capabilities(self):
        validate_image_model(self.model)
        validate_image_size(self.model, self.size)
        validate_image_options(
            self.model,
            quality=self.quality,
            output_format=self.output_format,
            response_format=self.response_format,
            background=self.background,
        )
        return self


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
