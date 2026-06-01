import json

from gva.core.hyperframes import prepare_hyperframes_scene_assets
from gva.models.storyboard import Scene, Storyboard, VisualSpec


def test_prepare_hyperframes_scene_assets_enhances_hook(tmp_path) -> None:
    renderer_dir = tmp_path / "renderer"
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration="不用再手动翻 README。",
                visual=VisualSpec(
                    layout="hook",
                    headline="这个项目能快速讲清楚",
                    bullets=["读取仓库", "生成脚本"],
                    accent_color="#111827",
                    animation="rise",
                ),
            )
        ],
    )

    enhanced = prepare_hyperframes_scene_assets(
        output_dir=tmp_path,
        renderer_dir=renderer_dir,
        storyboard=storyboard,
        render_strategy="remotion-primary",
    )

    scene = enhanced.scenes[0]
    assert scene.visual.enhanced_by == "hyperframes-lite"
    assert scene.visual.enhanced_html == "generated/hyperframes/scene-001.html"
    assert (tmp_path / "render-assets" / "hyperframes" / "scene-001.html").exists()
    assert (renderer_dir / "public" / "generated" / "hyperframes" / "scene-001.html").exists()

    manifest = json.loads((tmp_path / "logs" / "hyperframes-manifest.json").read_text(encoding="utf-8"))
    assert manifest["enhancer"] == "hyperframes-lite"
    assert manifest["mode"] == "remotion-primary"
    assert manifest["scene_assets"][0]["scene_id"] == "scene-001"


def test_prepare_hyperframes_scene_assets_can_enhance_all_scenes(tmp_path) -> None:
    renderer_dir = tmp_path / "renderer"
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="hook",
                start=0,
                duration=4,
                narration="不用再手动翻 README。",
                visual=VisualSpec(layout="hook", headline="快速讲清楚"),
            ),
            Scene(
                id="scene-002",
                type="flow",
                start=4,
                duration=6,
                narration="读取项目后生成讲解视频。",
                visual=VisualSpec(layout="flow", headline="核心流程", diagram_nodes=["读取", "分析", "生成"]),
            ),
        ],
    )

    enhanced = prepare_hyperframes_scene_assets(
        output_dir=tmp_path,
        renderer_dir=renderer_dir,
        storyboard=storyboard,
        render_strategy="hyperframes-primary",
    )

    assert all(scene.visual.enhanced_by == "hyperframes-lite" for scene in enhanced.scenes)
    manifest = json.loads((tmp_path / "logs" / "hyperframes-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "hyperframes-primary"
    assert len(manifest["scene_assets"]) == 2
