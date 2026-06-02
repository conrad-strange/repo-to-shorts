from __future__ import annotations

from gva.models.storyboard import MicroBeat, Storyboard


def tighten_storyboard_for_video_mode(storyboard: Storyboard, video_mode: str, repo_url: str | None = None) -> bool:
    """Apply deterministic pacing fixes after LLM storyboard generation."""
    changed = False
    for scene in storyboard.scenes:
        if scene.visual.layout != "cta" and scene.type != "cta":
            continue

        repo = _repo_handle(scene, repo_url)
        target_duration = _cta_target_duration(video_mode)
        narration = f"项目地址：{repo}。去 GitHub 查看代码，欢迎 Star。"
        bullets = ["查看代码", "阅读 README", "欢迎 Star"]
        micro_beats = [
            MicroBeat(text=repo, kind="cta", emphasis="GitHub", start_ratio=0.0),
            MicroBeat(text="查看代码", kind="cta", start_ratio=0.28),
            MicroBeat(text="欢迎 Star", kind="cta", start_ratio=0.56),
        ]

        if scene.visual.layout != "cta":
            scene.visual.layout = "cta"
            changed = True
        if scene.narration != narration:
            scene.narration = narration
            changed = True
        if scene.duration > target_duration:
            scene.duration = target_duration
            changed = True
        if scene.visual.headline != repo:
            scene.visual.headline = repo
            changed = True
        if scene.visual.bullets != bullets:
            scene.visual.bullets = bullets
            changed = True
        if scene.visual.caption != "开源项目":
            scene.visual.caption = "开源项目"
            changed = True
        if [beat.model_dump() for beat in scene.visual.micro_beats] != [beat.model_dump() for beat in micro_beats]:
            scene.visual.micro_beats = micro_beats
            changed = True
    return changed


def _cta_target_duration(video_mode: str) -> float:
    if video_mode == "technical_90s":
        return 6.0
    if video_mode == "standard_60s":
        return 5.0
    return 4.25


def _repo_handle(scene, repo_url: str | None = None) -> str:
    candidates = [
        repo_url,
        scene.visual.repo_display_url,
        scene.visual.repo_url,
        scene.visual.headline,
        *(beat.text for beat in scene.visual.micro_beats or []),
    ]
    for candidate in candidates:
        handle = _compact_repo_handle(candidate)
        if handle and "/" in handle:
            return handle
    return "owner/repo"


def _compact_repo_handle(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = (
        value.strip()
        .removeprefix("https://github.com/")
        .removeprefix("http://github.com/")
        .removeprefix("github.com/")
        .removesuffix(".git")
        .strip("/")
    )
    return cleaned or None
