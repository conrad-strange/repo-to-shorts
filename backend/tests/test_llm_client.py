import pytest

from gva.config import Settings
from gva.core.llm_client import (
    MissingApiKeyError,
    build_openai_client,
    get_generation_model,
    get_reasoning_model,
    has_real_api_key,
    llm_settings_error,
    normalize_llm_provider,
)


def test_deepseek_reasoning_model_setting() -> None:
    settings = Settings(
        llm_provider="deepseek",
        deepseek_api_key="test-key",
        deepseek_model_reasoning="deepseek-v4-pro",
    )
    assert get_reasoning_model(settings) == "deepseek-v4-pro"


def test_deepseek_requires_api_key() -> None:
    settings = Settings(llm_provider="deepseek", deepseek_api_key=None)
    with pytest.raises(MissingApiKeyError):
        build_openai_client(settings)


def test_placeholder_key_is_not_real() -> None:
    assert not has_real_api_key("your_deepseek_api_key_here")
    assert has_real_api_key("sk-real-looking-value")


def test_openai_compatible_provider_models() -> None:
    settings = Settings(
        llm_provider="openai-compatible",
        openai_compatible_api_key="test-key",
        openai_compatible_base_url="https://example.com/v1",
        openai_compatible_model_reasoning="reasoning-model",
        openai_compatible_model_generation="fast-model",
    )
    assert normalize_llm_provider(settings.llm_provider) == "openai_compatible"
    assert get_reasoning_model(settings) == "reasoning-model"
    assert get_generation_model(settings) == "fast-model"
    assert llm_settings_error(settings) is None


def test_openai_compatible_requires_base_url_and_model() -> None:
    settings = Settings(
        llm_provider="openai_compatible",
        openai_compatible_api_key="test-key",
        openai_compatible_base_url="",
        openai_compatible_model_generation="fast-model",
    )
    assert "OPENAI_COMPATIBLE_BASE_URL" in (llm_settings_error(settings) or "")

    settings.openai_compatible_base_url = "https://example.com/v1"
    settings.openai_compatible_model_generation = None
    assert "OPENAI_COMPATIBLE_MODEL_GENERATION" in (llm_settings_error(settings) or "")


def test_openai_compatible_requires_api_key() -> None:
    settings = Settings(
        llm_provider="custom",
        openai_compatible_api_key=None,
        openai_compatible_base_url="https://example.com/v1",
        openai_compatible_model_generation="fast-model",
    )
    with pytest.raises(MissingApiKeyError):
        build_openai_client(settings)
