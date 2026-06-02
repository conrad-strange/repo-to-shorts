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
        "your_openai_compatible_api_key_here",
        "your_api_key",
    }


def normalize_llm_provider(provider: str | None) -> str:
    normalized = (provider or "deepseek").strip().lower().replace("-", "_")
    if normalized in {"custom", "compatible", "openai_compatible"}:
        return "openai_compatible"
    return normalized


def get_reasoning_model(settings: Settings) -> str:
    provider = normalize_llm_provider(settings.llm_provider)
    if provider == "deepseek":
        return settings.deepseek_model_reasoning
    if provider == "openai":
        return settings.openai_model_reasoning
    if provider == "openai_compatible":
        return _first_model(
            settings.openai_compatible_model_reasoning,
            settings.openai_compatible_model_generation,
            name="OPENAI_COMPATIBLE_MODEL_REASONING",
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def get_generation_model(settings: Settings) -> str:
    provider = normalize_llm_provider(settings.llm_provider)
    if provider == "deepseek":
        return settings.deepseek_model_generation
    if provider == "openai":
        return settings.openai_model_generation
    if provider == "openai_compatible":
        return _first_model(
            settings.openai_compatible_model_generation,
            settings.openai_compatible_model_reasoning,
            name="OPENAI_COMPATIBLE_MODEL_GENERATION",
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def build_openai_client(settings: Settings) -> OpenAI:
    error = llm_settings_error(settings)
    if error:
        raise MissingApiKeyError(error)

    provider = normalize_llm_provider(settings.llm_provider)
    if provider == "deepseek":
        if not has_real_api_key(settings.deepseek_api_key):
            raise MissingApiKeyError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek.")
        return OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)

    if provider == "openai":
        if not has_real_api_key(settings.openai_api_key):
            raise MissingApiKeyError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    if provider == "openai_compatible":
        return OpenAI(
            api_key=settings.openai_compatible_api_key,
            base_url=settings.openai_compatible_base_url,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def llm_settings_error(settings: Settings) -> str | None:
    provider = normalize_llm_provider(settings.llm_provider)
    if provider == "deepseek":
        if not has_real_api_key(settings.deepseek_api_key):
            return "DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek."
        return None
    if provider == "openai":
        if not has_real_api_key(settings.openai_api_key):
            return "OPENAI_API_KEY is required when LLM_PROVIDER=openai."
        return None
    if provider == "openai_compatible":
        if not has_real_api_key(settings.openai_compatible_api_key):
            return "OPENAI_COMPATIBLE_API_KEY is required when LLM_PROVIDER=openai_compatible."
        if not (settings.openai_compatible_base_url or "").strip():
            return "OPENAI_COMPATIBLE_BASE_URL is required when LLM_PROVIDER=openai_compatible."
        if not (settings.openai_compatible_model_generation or settings.openai_compatible_model_reasoning):
            return "OPENAI_COMPATIBLE_MODEL_GENERATION is required when LLM_PROVIDER=openai_compatible."
        return None
    return f"Unsupported LLM_PROVIDER: {settings.llm_provider}"


def has_configured_llm(settings: Settings) -> bool:
    return llm_settings_error(settings) is None


def _first_model(*values: str | None, name: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    raise ValueError(f"{name} is required for LLM_PROVIDER=openai_compatible.")
