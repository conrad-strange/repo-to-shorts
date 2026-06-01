from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


class RenderConfig(BaseModel):
    storyboard_path: Path
    audio_path: Path | None = None
    output_path: Path
    fps: int = 30
    codec: Literal["h264"] = "h264"
    target_duration_seconds: int | None = None
    duration_strategy: Literal["auto", "short", "standard", "detailed"] = "auto"


class WorkflowResult(BaseModel):
    output_dir: Path
    metadata: dict[str, Any]
