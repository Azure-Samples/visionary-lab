from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any, Union
from models.common import BaseResponse
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
                                 description="Rewritten prompt for image generation")


class ImageGenerationRequest(BaseModel):
    """Request model for image generation"""

    # common parameters for gpt-image-1:
    prompt: str = Field(...,
                        description="User prompt for image generation. Maximum 32000 characters for gpt-image-1.",
                        examples=["A futuristic city skyline at sunset"])
    model: str = Field("gpt-image-1",
                       description="Image generation model to use",
                       examples=["gpt-image-1"])
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
