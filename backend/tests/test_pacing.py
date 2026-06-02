from gva.core.pacing import tighten_storyboard_for_video_mode
from gva.models.storyboard import MicroBeat, Scene, Storyboard, VisualSpec


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
