import pytest

from gva.config import Settings
from gva.core.llm_client import (
    MissingApiKeyError,
    build_openai_client,
    get_reasoning_model,
    has_real_api_key,
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
