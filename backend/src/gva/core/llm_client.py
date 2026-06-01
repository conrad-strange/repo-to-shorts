from __future__ import annotations

from openai import OpenAI

from gva.config import Settings


class MissingApiKeyError(RuntimeError):
    pass


def has_real_api_key(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return normalized not in {
        "",
        "your_api_key_here",
        "your_deepseek_api_key_here",
        "your_openai_api_key_here",
    }


def get_reasoning_model(settings: Settings) -> str:
    if settings.llm_provider == "deepseek":
        return settings.deepseek_model_reasoning
    if settings.llm_provider == "openai":
        return settings.openai_model_reasoning
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def get_generation_model(settings: Settings) -> str:
    if settings.llm_provider == "deepseek":
        return settings.deepseek_model_generation
    if settings.llm_provider == "openai":
        return settings.openai_model_generation
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def build_openai_client(settings: Settings) -> OpenAI:
    if settings.llm_provider == "deepseek":
        if not has_real_api_key(settings.deepseek_api_key):
            raise MissingApiKeyError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek.")
        return OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)

    if settings.llm_provider == "openai":
        if not has_real_api_key(settings.openai_api_key):
            raise MissingApiKeyError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
