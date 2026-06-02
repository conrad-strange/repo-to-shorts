from gva.agents.verifier import _soften_llm_verdict
from gva.models.storyboard import Scene, Storyboard, VisualSpec
from gva.workflow import _soften_risky_video_claims


def test_soften_risky_video_claims_removes_cloud_and_traceability_overclaims() -> None:
    storyboard = Storyboard(
        title="Demo",
        scenes=[
            Scene(
                id="scene-001",
                type="text",
                start=0,
                duration=4,
                narration="这个项目可以快速定位答案，并给出可追溯来源，无需任何云服务。",
                visual=VisualSpec(layout="text", headline="来源追踪", bullets=["无需云服务"]),
            )
        ],
    )

    assert _soften_risky_video_claims(storyboard)
    scene = storyboard.scenes[0]
    assert "可追溯来源" not in scene.narration
    assert "无需任何云服务" not in scene.narration
    assert scene.visual.headline == "相关段落"
    assert scene.visual.bullets == ["按项目配置接入模型服务"]


def test_audience_framing_is_not_high_risk_blocker() -> None:
    status, severity, reason = _soften_llm_verdict(
        text="这个工具专门为AI研究者和学生设计。",
        evidence_refs=["local_rag"],
        status="unsupported",
        severity="high",
        reason="The evidence does not explicitly mention students.",
    )

    assert status == "weak"
    assert severity == "medium"
    assert "editable positioning" in reason
