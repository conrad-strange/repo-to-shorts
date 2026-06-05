from __future__ import annotations

from gva.models.storyboard import MicroBeat, Scene, Storyboard


VIDEO_MODE_DURATION_RANGES: dict[str, tuple[float, float]] = {
    "short_30s": (30.0, 59.0),
    "standard_60s": (60.0, 89.0),
    "technical_90s": (90.0, 120.0),
}


def duration_range_for_video_mode(video_mode: str) -> tuple[float, float]:
    return VIDEO_MODE_DURATION_RANGES.get(video_mode, VIDEO_MODE_DURATION_RANGES["standard_60s"])


def fit_storyboard_duration_for_video_mode(storyboard: Storyboard, video_mode: str) -> bool:
    """Keep storyboard timing inside the product's selected duration bucket."""
    if not storyboard.scenes:
        return False

    minimum, maximum = duration_range_for_video_mode(video_mode)
    changed = _normalize_storyboard_timing(storyboard)
    total = _storyboard_duration(storyboard)

    if total < minimum:
        changed = _expand_storyboard_to_minimum(storyboard, minimum) or changed
    elif total > maximum:
        changed = _shrink_storyboard_to_maximum(storyboard, maximum) or changed

    if changed:
        _normalize_storyboard_timing(storyboard)
    return changed


def tighten_storyboard_for_video_mode(storyboard: Storyboard, video_mode: str, repo_url: str | None = None) -> bool:
    """Apply deterministic pacing fixes after LLM storyboard generation."""
    changed = _tighten_opening_scene(storyboard)
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


def _tighten_opening_scene(storyboard: Storyboard) -> bool:
    if not storyboard.scenes:
        return False
    first = storyboard.scenes[0]
    if _is_cta_scene(first):
        return False

    changed = False
    narration = _short_hook_narration(first.narration)
    if narration != first.narration:
        first.narration = narration
        changed = True
    if first.duration > 4.0:
        first.duration = 3.8
        changed = True
    return changed


def _short_hook_narration(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return cleaned
    pieces = []
    current = ""
    for char in cleaned:
        current += char
        if char in "。！？!?；;":
            pieces.append(current.strip())
            current = ""
    if current.strip():
        pieces.append(current.strip())
    if pieces and len(pieces[0]) >= 10:
        return pieces[0]
    if len(cleaned) <= 42:
        return cleaned
    return cleaned[:42].rstrip("，,、；; ") + "。"


def _cta_target_duration(video_mode: str) -> float:
    if video_mode == "technical_90s":
        return 6.0
    if video_mode == "standard_60s":
        return 5.0
    return 4.25


def _shrink_storyboard_to_maximum(storyboard: Storyboard, maximum: float) -> bool:
    overflow = _storyboard_duration(storyboard) - maximum
    if overflow <= 0:
        return False

    candidates = _shrink_candidates(storyboard)
    remaining = overflow
    while candidates and remaining > 0.005:
        share = remaining / len(candidates)
        removed = 0.0
        next_candidates = []
        for index, scene in candidates:
            floor = _scene_minimum_duration(index, scene)
            room = max(0.0, scene.duration - floor)
            reduction = min(share, room)
            if reduction > 0:
                scene.duration -= reduction
                removed += reduction
            if room - reduction > 0.005:
                next_candidates.append((index, scene))
        if removed <= 0.005:
            break
        remaining -= removed
        candidates = next_candidates
    return True


def _expand_storyboard_to_minimum(storyboard: Storyboard, minimum: float) -> bool:
    deficit = minimum - _storyboard_duration(storyboard)
    if deficit <= 0:
        return False

    candidates = _expand_candidates(storyboard)
    if not candidates:
        return False

    share = deficit / len(candidates)
    for _index, scene in candidates:
        scene.duration = round(scene.duration + share, 2)
    return True


def _expand_candidates(storyboard: Storyboard) -> list[tuple[int, Scene]]:
    candidates = [
        (index, scene)
        for index, scene in enumerate(storyboard.scenes)
        if index > 0 and not _is_cta_scene(scene)
    ]
    if candidates:
        return candidates
    return [
        (index, scene)
        for index, scene in enumerate(storyboard.scenes)
        if index > 0
    ]


def _shrink_candidates(storyboard: Storyboard) -> list[tuple[int, Scene]]:
    return [
        (index, scene)
        for index, scene in enumerate(storyboard.scenes)
        if scene.duration > _scene_minimum_duration(index, scene) + 0.005
    ]


def _scene_minimum_duration(_index: int, _scene: Scene) -> float:
    return 2.5


def _is_cta_scene(scene: Scene) -> bool:
    return scene.visual.layout == "cta" or scene.type == "cta"


def _normalize_storyboard_timing(storyboard: Storyboard) -> bool:
    current = 0.0
    changed = False
    for scene in storyboard.scenes:
        duration = max(2.5, round(float(scene.duration), 2))
        start = round(current, 2)
        if scene.start != start or scene.duration != duration:
            changed = True
        scene.start = start
        scene.duration = duration
        current += duration
    return changed


def _storyboard_duration(storyboard: Storyboard) -> float:
    return round(sum(scene.duration for scene in storyboard.scenes), 2)


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
