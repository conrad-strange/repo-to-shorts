from gva.models.storyboard import MicroBeat, Scene, Storyboard, VisualSpec


def test_storyboard_model_accepts_minimal_scene() -> None:
    scene = Scene(
        id="scene-001",
        type="title",
        start=0,
        duration=5,
        narration="这是一个测试。",
        visual=VisualSpec(layout="title", headline="测试项目"),
    )
    storyboard = Storyboard(title="测试", scenes=[scene])
    assert storyboard.width == 1080
    assert storyboard.aspect_ratio == "9:16"


def test_visual_spec_accepts_micro_beats() -> None:
    visual = VisualSpec(
        layout="flow",
        headline="核心流程",
        micro_beats=[MicroBeat(text="读取仓库", kind="flow", start_ratio=0.1)],
    )
    assert visual.micro_beats[0].text == "读取仓库"


def test_visual_spec_accepts_asset_fields() -> None:
    visual = VisualSpec(
        layout="github_hero",
        headline="真实仓库开场",
        asset_type="github_repo_home",
        asset_path="generated/assets/github-repo-home.png",
        focus_target="repo_name",
        repo_display_url="github.com/example/demo",
    )
    assert visual.asset_type == "github_repo_home"
    assert visual.focus_target == "repo_name"
    assert visual.repo_display_url == "github.com/example/demo"
