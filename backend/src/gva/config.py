from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or .env."""

    llm_provider: str = "deepseek"

    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_reasoning: str = "deepseek-v4-pro"
    deepseek_model_generation: str = "deepseek-v4-flash"

    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model_reasoning: str = "gpt-5.2"
    openai_model_generation: str = "gpt-5-mini"

    tts_provider: str = "edge"
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+25%"
    scene_enhancer: str = "hyperframes-lite"
    render_strategy: str = "remotion-primary"
    hyperframes_cmd: Optional[Path] = None

    renderer_dir: Path = Path("renderer")
    outputs_dir: Path = Path("outputs")
    repo_cache_dir: Path = Path(".cache/repos")
    node_exe: Optional[Path] = None
    npm_cmd: Optional[Path] = None
    ffmpeg_exe: Optional[Path] = None
    chrome_exe: Optional[Path] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
