from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class TtsSceneAudio(BaseModel):
    scene_id: str
    narration: str
    audio_path: Path
    duration_seconds: float
    original_scene_duration_seconds: float
    adjusted_scene_duration_seconds: float


class TtsManifest(BaseModel):
    provider: Literal["edge"] = "edge"
    voice: str
    rate: str = "unknown"
    full_audio_path: Path
    full_audio_duration_seconds: float
    scenes: list[TtsSceneAudio] = Field(default_factory=list)


class TimingAdjustmentLog(BaseModel):
    storyboard_path: Path
    timed_storyboard_path: Path
    tts_manifest_path: Path
    original_total_duration_seconds: float
    adjusted_total_duration_seconds: float
    method: str
