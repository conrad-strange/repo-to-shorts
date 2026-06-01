from typing import Literal

from pydantic import BaseModel, Field


class ScriptSegment(BaseModel):
    scene_hint: str
    narration: str
    evidence_keys: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class VideoScript(BaseModel):
    language: Literal["zh-CN"] = "zh-CN"
    duration_seconds: int | None = Field(
        default=None,
        description="Estimated duration. Final timing can be adjusted after TTS.",
    )
    title: str
    segments: list[ScriptSegment]
    full_text: str
