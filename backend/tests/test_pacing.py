from gva.core.pacing import (
    duration_range_for_video_mode,
    fit_storyboard_duration_for_video_mode,
    tighten_storyboard_for_video_mode,
)
from gva.models.storyboard import MicroBeat, Scene, Storyboard, VisualSpec


def _scene(scene_id: str, layout: str, duration: float) -> Scene:
    return Scene(
        id=scene_id,
        type=layout,
        start=0,
        duration=duration,
        narration=f"Narration for {scene_id}",
        visual=VisualSpec(layout=layout, headline=scene_id),
    )


def test_duration_range_for_video_mode_matches_product_buckets() -> None:
    assert duration_range_for_video_mode("short_30s") == (30.0, 59.0)
    assert duration_range_for_video_mode("standard_60s") == (60.0, 89.0)
    assert duration_range_for_video_mode("technical_90s") == (90.0, 120.0)


def test_fit_storyboard_duration_pads_short_storyboard_to_selected_bucket() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            _scene("scene-001", "github_hero", 3),
            _scene("scene-002", "readme_focus", 10),
            _scene("scene-003", "architecture_map", 10),
            _scene("scene-004", "feature_spotlight", 10),
            _scene("scene-005", "evidence_grid", 10),
            _scene("scene-006", "cta", 5),
        ],
    )

    changed = fit_storyboard_duration_for_video_mode(storyboard, "technical_90s")

    assert changed
    assert round(sum(scene.duration for scene in storyboard.scenes), 2) == 90.0
    assert storyboard.scenes[0].duration == 3
    assert storyboard.scenes[-1].duration == 5
    assert all(scene.duration > 10 for scene in storyboard.scenes[1:-1])
    cursor = 0.0
    for scene in storyboard.scenes:
        assert scene.start == round(cursor, 2)
        cursor += scene.duration


def test_fit_storyboard_duration_shrinks_standard_mode_to_maximum() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            _scene("scene-001", "github_hero", 4),
            _scene("scene-002", "readme_focus", 35),
            _scene("scene-003", "architecture_map", 35),
            _scene("scene-004", "feature_spotlight", 35),
            _scene("scene-005", "evidence_grid", 35),
            _scene("scene-006", "cta", 10),
        ],
    )

    changed = fit_storyboard_duration_for_video_mode(storyboard, "standard_60s")

    assert changed
    assert round(sum(scene.duration for scene in storyboard.scenes), 2) == 89.0
    assert storyboard.scenes[0].start == 0
    assert storyboard.scenes[-1].start + storyboard.scenes[-1].duration == 89.0


def test_tighten_storyboard_for_video_mode_shortens_cta() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="cta",
                start=0,
                duration=9,
                narration="这是很长的结尾说明，会让最后一幕拖得太久。",
                visual=VisualSpec(
                    layout="cta",
                    headline="github.com/example/demo",
                    bullets=["Old"],
                    micro_beats=[MicroBeat(text="example/demo", kind="cta")],
                ),
            )
        ],
    )

    changed = tighten_storyboard_for_video_mode(storyboard, "short_30s")

    assert changed
    scene = storyboard.scenes[0]
    assert scene.duration == 4.25
    assert scene.narration == "项目地址：example/demo。去 GitHub 查看代码，欢迎 Star。"
    assert scene.visual.headline == "example/demo"
    assert scene.visual.bullets == ["查看代码", "阅读 README", "欢迎 Star"]


def test_tighten_storyboard_shortens_long_opening_scene() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=8,
                narration="花了两周写代码，却连一个30秒的介绍视频都挤不出来？或者更糟，拍出来全是大厂话术。",
                visual=VisualSpec(layout="github_hero", headline="两周代码，30秒介绍都憋不出？"),
            ),
            _scene("scene-002", "text", 8),
        ],
    )

    changed = tighten_storyboard_for_video_mode(storyboard, "standard_60s")

    assert changed
    assert storyboard.scenes[0].duration == 3.8
    assert storyboard.scenes[0].narration == "花了两周写代码，却连一个30秒的介绍视频都挤不出来？"


def test_tighten_storyboard_uses_repo_url_for_cta_with_wrong_layout() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="cta",
                start=0,
                duration=5,
                narration="项目地址：owner/repo。",
                visual=VisualSpec(layout="github_hero", headline="owner/repo"),
            )
        ],
    )

    changed = tighten_storyboard_for_video_mode(
        storyboard,
        "short_30s",
        repo_url="https://github.com/aerdem4/lofo-importance",
    )

    assert changed
    scene = storyboard.scenes[0]
    assert scene.visual.layout == "cta"
    assert scene.visual.headline == "aerdem4/lofo-importance"
    assert scene.narration == "项目地址：aerdem4/lofo-importance。去 GitHub 查看代码，欢迎 Star。"
