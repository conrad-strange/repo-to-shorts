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
    render_strategy: str = "remotion-primary"
    video_mode: str = "standard_60s"
    render_profile: str = "final"
    brand_mode: str = "rs"
    bomb_circle: str = "科技圈"
    bomb_again_count: int = 1
    rb_tts_voice: str = "zh-CN-YunxiNeural"
    rb_tts_rate: str = "+38%"
    rb_hook_duration_seconds: float = 3.0
    remotion_concurrency: Optional[int] = None
    repair_enabled: bool = True
    repair_max_attempts: int = 1

    renderer_dir: Path = Path("renderer")
    frontend_dir: Path = Path("frontend")
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
