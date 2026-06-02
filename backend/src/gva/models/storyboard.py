from typing import Literal

from pydantic import BaseModel, Field


SceneLayout = Literal[
    "hook",
    "github_hero",
    "title",
    "text",
    "readme_focus",
    "feature_spotlight",
    "architecture_map",
    "evidence_grid",
    "code",
    "result_media",
    "flow",
    "stack",
    "steps",
    "cta",
]
SceneAnimation = Literal["fade", "slide", "rise", "zoom", "none"]
MicroBeatKind = Literal["text", "metric", "code", "flow", "warning", "cta"]
VisualAssetType = Literal["github_repo_home", "readme_focus", "none"]
VisualFocusTarget = Literal["repo_name", "readme_title", "install_command", "readme_section", "none"]


class MicroBeat(BaseModel):
    text: str
    kind: MicroBeatKind = "text"
    emphasis: str | None = None
    start_ratio: float = 0.0


class CaptionCue(BaseModel):
    start: float
    end: float
    text: str
    keywords: list[str] = Field(default_factory=list)
    source_scene_id: str


class VisualSpec(BaseModel):
    layout: SceneLayout
    headline: str
    bullets: list[str] = Field(default_factory=list)
    code: str | None = None
    diagram_nodes: list[str] = Field(default_factory=list)
    icons: list[str] = Field(default_factory=list)
    accent_color: str = "#111827"
    animation: SceneAnimation = "rise"
    micro_beats: list[MicroBeat] = Field(default_factory=list)
    caption: str | None = None
    asset_type: VisualAssetType = "none"
    asset_path: str | None = None
    focus_target: VisualFocusTarget = "none"
    repo_url: str | None = None
    repo_display_url: str | None = None
    media_type: Literal["image", "video", "none"] = "none"
    evidence_refs: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    id: str
    type: str
    start: float
    duration: float
    narration: str
    visual: VisualSpec
    evidence_keys: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    captions: list[CaptionCue] = Field(default_factory=list)


class Storyboard(BaseModel):
    title: str
    aspect_ratio: Literal["9:16"] = "9:16"
    fps: int = 30
    width: int = 1080
    height: int = 1920
    scenes: list[Scene]
