"""Single source of truth for image-model capabilities exposed by the app."""

from __future__ import annotations

import re
from math import gcd
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, computed_field


GPT_IMAGE_2_MODEL = "gpt-image-2"
FLUX_KONTEXT_PRO_MODEL = "flux-kontext-pro"
SUPPORTED_IMAGE_MODELS = (GPT_IMAGE_2_MODEL, FLUX_KONTEXT_PRO_MODEL)

ImageProvider = Literal["azure", "openai"]

_GPT_IMAGE_2_MIN_PIXELS = 655_360
_GPT_IMAGE_2_MAX_PIXELS = 8_294_400
_GPT_IMAGE_2_MAX_EDGE = 3_840
_GPT_IMAGE_2_MAX_ASPECT_RATIO = 3
_IMAGE_SIZE_PATTERN = re.compile(r"^(?P<width>[1-9]\d*)x(?P<height>[1-9]\d*)$")

_STANDARD_SIZES = ("auto", "1024x1024", "1536x1024", "1024x1536")
_GPT_IMAGE_2_RECOMMENDED_SIZES = (
    *_STANDARD_SIZES,
    "2048x2048",
    "3840x2160",
    "2160x3840",
)


class ImageModelCapabilities(BaseModel):
    """Serializable capability disclosure for one model/provider combination."""

    model_config = ConfigDict(frozen=True)

    model: str
    display_name: str
    provider: ImageProvider
    max_reference_images: int
    max_outputs_per_request: int
    supports_mask: bool
    input_fidelity_options: tuple[str, ...]
    output_formats: tuple[str, ...]
    response_format: Literal["b64_json", "url"]
    background_options: tuple[str, ...]
    quality_options: tuple[str, ...]
    recommended_sizes: tuple[str, ...]
    supports_custom_sizes: bool
    disclosure: str

    @computed_field
    @property
    def supports_multiple_reference_images(self) -> bool:
        return self.max_reference_images > 1

    @computed_field
    @property
    def supports_transparency(self) -> bool:
        return "transparent" in self.background_options

    def to_public_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible disclosure payload for a future endpoint."""

        return self.model_dump(mode="json")


def get_image_model_capabilities(
    model: str, *, provider: str = "azure"
) -> ImageModelCapabilities:
    """Resolve model limits without duplicating conditionals in callers."""

    normalized_provider = provider.strip().lower()
    if normalized_provider not in {"azure", "openai"}:
        raise ValueError("Image provider must be 'azure' or 'openai'")
    typed_provider = cast(ImageProvider, normalized_provider)

    if model == GPT_IMAGE_2_MODEL:
        output_formats = (
            ("png", "jpeg")
            if typed_provider == "azure"
            else ("png", "jpeg", "webp")
        )
        return ImageModelCapabilities(
            model=model,
            display_name="GPT-Image-2",
            provider=typed_provider,
            max_reference_images=10,
            max_outputs_per_request=10,
            supports_mask=True,
            input_fidelity_options=("low", "high"),
            output_formats=output_formats,
            response_format="b64_json",
            background_options=("auto", "transparent", "opaque"),
            quality_options=("auto", "low", "medium", "high"),
            recommended_sizes=_GPT_IMAGE_2_RECOMMENDED_SIZES,
            supports_custom_sizes=True,
            disclosure=(
                "Supports text generation, high-fidelity editing, and up to 10 "
                "ordered reference images. Best fit for multi-image storylines."
            ),
        )

    if model == FLUX_KONTEXT_PRO_MODEL:
        if typed_provider != "azure":
            raise ValueError("FLUX Kontext is only configured through Azure")
        return ImageModelCapabilities(
            model=model,
            display_name="FLUX Kontext Pro",
            provider=typed_provider,
            max_reference_images=1,
            max_outputs_per_request=1,
            supports_mask=False,
            input_fidelity_options=(),
            output_formats=("png", "jpeg"),
            response_format="url",
            background_options=("auto",),
            quality_options=(),
            recommended_sizes=_STANDARD_SIZES,
            supports_custom_sizes=True,
            disclosure=(
                "Supports storylines with one primary image anchor and one output "
                "per request. Additional references are distilled into text, which "
                "may reduce visual fidelity."
            ),
        )

    raise ValueError(f"Model must be one of {list(SUPPORTED_IMAGE_MODELS)}")


def get_configured_image_model_capabilities(
    config: Any | None = None,
) -> tuple[ImageModelCapabilities, ...]:
    """Return only models whose required provider configuration is present."""

    if config is None:
        from backend.core.config import settings

        config = settings

    provider = str(config.MODEL_PROVIDER).strip().lower()
    capabilities: list[ImageModelCapabilities] = []
    if provider == "azure":
        if getattr(config, "IMAGEGEN_2_DEPLOYMENT", None):
            capabilities.append(
                get_image_model_capabilities(GPT_IMAGE_2_MODEL, provider=provider)
            )
        if getattr(config, "FLUX_KONTEXT_DEPLOYMENT", None):
            capabilities.append(
                get_image_model_capabilities(
                    FLUX_KONTEXT_PRO_MODEL, provider=provider
                )
            )
    elif provider == "openai":
        if getattr(config, "OPENAI_API_KEY", None):
            capabilities.append(
                get_image_model_capabilities(GPT_IMAGE_2_MODEL, provider=provider)
            )
    else:
        raise ValueError("Image provider must be 'azure' or 'openai'")
    return tuple(capabilities)


def validate_reference_image_count(
    model: str, count: int, *, provider: str = "azure"
) -> None:
    capabilities = get_image_model_capabilities(model, provider=provider)
    if count < 0 or count > capabilities.max_reference_images:
        raise ValueError(
            f"{capabilities.display_name} supports at most "
            f"{capabilities.max_reference_images} reference image(s)"
        )


def validate_image_output_constraints(
    model: str,
    *,
    provider: str = "azure",
    output_count: int = 1,
    output_format: str = "png",
    background: str = "auto",
) -> None:
    capabilities = get_image_model_capabilities(model, provider=provider)
    if not 1 <= output_count <= capabilities.max_outputs_per_request:
        raise ValueError(
            f"{capabilities.display_name} supports between 1 and "
            f"{capabilities.max_outputs_per_request} output image(s) per request"
        )
    if output_format not in capabilities.output_formats:
        raise ValueError(
            f"{capabilities.display_name} output_format must be one of "
            f"{list(capabilities.output_formats)} for {capabilities.provider}"
        )
    if background not in capabilities.background_options:
        raise ValueError(
            f"{capabilities.display_name} background must be one of "
            f"{list(capabilities.background_options)}"
        )
    if background == "transparent" and output_format not in {"png", "webp"}:
        raise ValueError("Transparent backgrounds require png or webp output")


def compatible_image_sizes(model: str, *, provider: str = "azure") -> tuple[str, ...]:
    return get_image_model_capabilities(model, provider=provider).recommended_sizes


def validate_compatible_image_size(model: str, size: str) -> None:
    """Validate dimensions according to the behavior implemented by each adapter."""

    if model not in SUPPORTED_IMAGE_MODELS:
        raise ValueError(f"Model must be one of {list(SUPPORTED_IMAGE_MODELS)}")
    if size == "auto":
        return
    match = _IMAGE_SIZE_PATTERN.fullmatch(size)
    if not match:
        raise ValueError("Image size must be 'auto' or WIDTHxHEIGHT")
    width = int(match.group("width"))
    height = int(match.group("height"))

    if model == GPT_IMAGE_2_MODEL:
        if width % 16 or height % 16:
            raise ValueError("GPT-Image-2 width and height must be multiples of 16")
        if max(width, height) > _GPT_IMAGE_2_MAX_EDGE:
            raise ValueError(
                f"GPT-Image-2 long edge must not exceed {_GPT_IMAGE_2_MAX_EDGE} pixels"
            )
        if max(width, height) > _GPT_IMAGE_2_MAX_ASPECT_RATIO * min(width, height):
            raise ValueError("GPT-Image-2 aspect ratio must be between 1:3 and 3:1")
        pixels = width * height
        if not _GPT_IMAGE_2_MIN_PIXELS <= pixels <= _GPT_IMAGE_2_MAX_PIXELS:
            raise ValueError(
                "GPT-Image-2 total pixels must be between "
                f"{_GPT_IMAGE_2_MIN_PIXELS:,} and {_GPT_IMAGE_2_MAX_PIXELS:,}"
            )
        return

    if model == FLUX_KONTEXT_PRO_MODEL:
        # The adapter reduces requested dimensions to an aspect ratio before sending.
        divisor = gcd(width, height)
        if divisor <= 0:
            raise ValueError("FLUX Kontext dimensions must be positive")
        return


def is_compatible_image_size(model: str, size: str) -> bool:
    try:
        validate_compatible_image_size(model, size)
    except ValueError:
        return False
    return True
