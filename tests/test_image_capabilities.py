from types import SimpleNamespace

import pytest

from backend.core.image_capabilities import (
    FLUX_KONTEXT_PRO_MODEL,
    GPT_IMAGE_2_MODEL,
    compatible_image_sizes,
    get_configured_image_model_capabilities,
    get_image_model_capabilities,
    is_compatible_image_size,
    validate_image_output_constraints,
    validate_reference_image_count,
)


def test_gpt_image_capabilities_disclose_storyline_support():
    capabilities = get_image_model_capabilities(GPT_IMAGE_2_MODEL, provider="azure")

    assert capabilities.max_reference_images == 10
    assert capabilities.max_outputs_per_request == 10
    assert capabilities.supports_multiple_reference_images is True
    assert capabilities.supports_mask is True
    assert capabilities.input_fidelity_options == ("low", "high")
    assert capabilities.output_formats == ("png", "jpeg")
    assert capabilities.response_format == "b64_json"
    assert "Best fit for multi-image storylines" in capabilities.disclosure


def test_openai_gpt_capabilities_include_webp():
    capabilities = get_image_model_capabilities(GPT_IMAGE_2_MODEL, provider="openai")

    assert capabilities.output_formats == ("png", "jpeg", "webp")
    validate_image_output_constraints(
        GPT_IMAGE_2_MODEL,
        provider="openai",
        output_format="webp",
        background="transparent",
    )


def test_capability_disclosure_can_be_serialized_for_a_public_endpoint():
    payload = get_image_model_capabilities(GPT_IMAGE_2_MODEL).to_public_dict()

    assert payload["model"] == GPT_IMAGE_2_MODEL
    assert payload["recommended_sizes"][0] == "auto"
    assert payload["supports_multiple_reference_images"] is True
    assert payload["supports_transparency"] is True
    assert isinstance(payload["disclosure"], str)


def test_flux_capabilities_disclose_single_reference_and_output():
    capabilities = get_image_model_capabilities(
        FLUX_KONTEXT_PRO_MODEL, provider="azure"
    )

    assert capabilities.max_reference_images == 1
    assert capabilities.max_outputs_per_request == 1
    assert capabilities.supports_multiple_reference_images is False
    assert capabilities.supports_mask is False
    assert capabilities.response_format == "url"
    assert "one primary image anchor" in capabilities.disclosure
    assert "distilled into text" in capabilities.disclosure

    with pytest.raises(ValueError, match="at most 1 reference"):
        validate_reference_image_count(FLUX_KONTEXT_PRO_MODEL, 2)
    with pytest.raises(ValueError, match="between 1 and 1 output"):
        validate_image_output_constraints(
            FLUX_KONTEXT_PRO_MODEL,
            output_count=2,
        )


def test_azure_output_constraints_reject_webp_and_transparent_jpeg():
    with pytest.raises(ValueError, match="output_format"):
        validate_image_output_constraints(
            GPT_IMAGE_2_MODEL,
            provider="azure",
            output_format="webp",
        )
    with pytest.raises(ValueError, match="Transparent backgrounds"):
        validate_image_output_constraints(
            GPT_IMAGE_2_MODEL,
            provider="azure",
            output_format="jpeg",
            background="transparent",
        )


def test_compatible_sizes_share_the_backend_dimension_rules():
    assert "3840x2160" in compatible_image_sizes(GPT_IMAGE_2_MODEL)
    assert is_compatible_image_size(GPT_IMAGE_2_MODEL, "1280x768") is True
    assert is_compatible_image_size(GPT_IMAGE_2_MODEL, "1025x1024") is False
    assert is_compatible_image_size(FLUX_KONTEXT_PRO_MODEL, "1600x900") is True
    assert is_compatible_image_size(FLUX_KONTEXT_PRO_MODEL, "bad-size") is False


def test_configured_capabilities_only_include_available_deployments():
    azure_config = SimpleNamespace(
        MODEL_PROVIDER="azure",
        IMAGEGEN_2_DEPLOYMENT="gpt-image-2",
        FLUX_KONTEXT_DEPLOYMENT=None,
        OPENAI_API_KEY=None,
    )
    openai_config = SimpleNamespace(
        MODEL_PROVIDER="openai",
        IMAGEGEN_2_DEPLOYMENT=None,
        FLUX_KONTEXT_DEPLOYMENT=None,
        OPENAI_API_KEY="test-key",
    )

    azure_models = get_configured_image_model_capabilities(azure_config)
    openai_models = get_configured_image_model_capabilities(openai_config)

    assert [item.model for item in azure_models] == [GPT_IMAGE_2_MODEL]
    assert [item.model for item in openai_models] == [GPT_IMAGE_2_MODEL]


def test_flux_is_not_exposed_for_direct_openai_provider():
    with pytest.raises(ValueError, match="only configured through Azure"):
        get_image_model_capabilities(
            FLUX_KONTEXT_PRO_MODEL,
            provider="openai",
        )


def test_unknown_model_is_never_size_compatible():
    assert is_compatible_image_size("unknown-model", "auto") is False
