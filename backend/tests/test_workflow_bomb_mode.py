from gva.config import Settings
from gva.models.storyboard import MicroBeat, Scene, Storyboard, VisualSpec
from gva.workflow import _apply_bomb_mode_to_storyboard


def test_bomb_mode_preserves_web_editor_copy_and_beats() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="github_hero",
                start=0,
                duration=6,
                narration="用户改过的旁白。",
                visual=VisualSpec(
                    layout="github_hero",
                    headline="用户改过的标题",
                    caption="用户改过的画面短句",
                    micro_beats=[
                        MicroBeat(text="用户标签一"),
                        MicroBeat(text="用户标签二"),
                    ],
                ),
            )
        ],
    )
    settings = Settings(brand_mode="rb", bomb_circle="科技圈", bomb_again_count=1)

    changed = _apply_bomb_mode_to_storyboard(
        storyboard,
        settings,
        "https://github.com/conrad-strange/repo-to-shorts",
        preserve_user_copy=True,
    )

    first = storyboard.scenes[0]
    assert changed
    assert first.type == "bomb_hook"
    assert first.visual.layout == "github_hero"
    assert first.visual.headline == "用户改过的标题"
    assert first.visual.caption == "用户改过的画面短句"
    assert first.narration == "用户改过的旁白。"
    assert [beat.text for beat in first.visual.micro_beats] == ["用户标签一", "用户标签二"]
