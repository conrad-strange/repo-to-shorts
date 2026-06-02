from gva.agents.repair_writer import apply_repair_payload
from gva.models.script import ScriptSegment, VideoScript
from gva.models.storyboard import Scene, Storyboard, VisualSpec


def test_apply_repair_payload_updates_script_and_storyboard() -> None:
    script = VideoScript(
        title="Demo",
        segments=[
            ScriptSegment(scene_hint="hook", narration="Unsupported claim."),
            ScriptSegment(scene_hint="cta", narration="Old CTA."),
        ],
        full_text="Unsupported claim.Old CTA.",
    )
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="text",
                start=0,
                duration=5,
                narration="Unsupported claim.",
                visual=VisualSpec(layout="text", headline="Too much text", bullets=["Unsupported"]),
            )
        ],
    )

    changes = apply_repair_payload(
        script,
        storyboard,
        {
            "script_segments": [{"index": 1, "narration": "Evidence-backed rewrite."}],
            "storyboard_scenes": [
                {
                    "id": "scene-001",
                    "narration": "Evidence-backed rewrite.",
                    "visual": {
                        "headline": "Evidence",
                        "caption": "Repo backed",
                        "bullets": ["README", "Code"],
                        "micro_beats": [{"text": "README", "kind": "unknown", "start_ratio": 0.2}],
                    },
                }
            ],
        },
    )

    assert changes
    assert script.segments[0].narration == "Evidence-backed rewrite."
    assert script.full_text == "Evidence-backed rewrite.Old CTA."
    assert storyboard.scenes[0].narration == "Evidence-backed rewrite."
    assert storyboard.scenes[0].visual.headline == "Evidence"
    assert storyboard.scenes[0].visual.bullets == ["README", "Code"]
    assert storyboard.scenes[0].visual.micro_beats[0].kind == "text"


def test_apply_repair_payload_normalizes_readme_typo() -> None:
    script = VideoScript(
        title="Demo",
        segments=[ScriptSegment(scene_hint="readme", narration="Old.")],
        full_text="Old.",
    )
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="readme_focus",
                start=0,
                duration=5,
                narration="Old.",
                visual=VisualSpec(layout="readme_focus", headline="README", bullets=[]),
            )
        ],
    )

    apply_repair_payload(
        script,
        storyboard,
        {
            "script_segments": [{"index": 1, "narration": "READNE 内容来自仓库。"}],
            "storyboard_scenes": [
                {
                    "id": "scene-001",
                    "visual": {
                        "headline": "READNE 证据",
                        "bullets": ["Readne 摘要"],
                    },
                }
            ],
        },
    )

    assert script.segments[0].narration == "README 内容来自仓库。"
    assert storyboard.scenes[0].visual.headline == "README 证据"
    assert storyboard.scenes[0].visual.bullets == ["README 摘要"]
