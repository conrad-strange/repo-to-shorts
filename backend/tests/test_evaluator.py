from gva.agents.evaluator import (
    _evaluate_visible_text_manifest,
    _is_vertical_9_16,
    _parse_video_resolution,
    render_evaluation_markdown,
)
from gva.models.evaluation import EvaluationIssue, EvaluationReport


def test_render_evaluation_markdown_includes_issue() -> None:
    report = EvaluationReport(
        passed=False,
        score=75,
        issues=[
            EvaluationIssue(
                severity="medium",
                category="visual",
                message="Too many bullets.",
                suggestion="Use fewer bullets.",
            )
        ],
        metrics={"scene_count": 6},
    )
    text = render_evaluation_markdown(report)
    assert "Too many bullets" in text
    assert "`scene_count`: 6" in text


def test_preview_resolution_counts_as_vertical_9_16() -> None:
    output = (
        "Stream #0:0: Video: h264, yuv420p, "
        "540x960 [SAR 1:1 DAR 9:16], 30 fps"
    )
    resolution = _parse_video_resolution(output)
    assert resolution == "540x960"
    assert _is_vertical_9_16(output, resolution)


def test_visible_text_manifest_issues_are_evaluated() -> None:
    issues: list[EvaluationIssue] = []
    metrics = {}
    _evaluate_visible_text_manifest(
        {
            "issues": [
                {
                    "scene_id": "scene-001",
                    "source": "visual.headline",
                    "message": "scene-001 visual.headline repeats narration",
                }
            ],
            "scenes": [
                {
                    "scene_id": "scene-001",
                    "entries": [
                        {"source": "visual.headline", "text": "旁白句子", "allowed_from_narration": False},
                        {"source": "captions[0].text", "text": "旁白句子", "allowed_from_narration": True},
                    ],
                }
            ],
        },
        issues,
        metrics,
    )

    assert metrics["visible_text_issue_count"] == 1
    assert metrics["visible_text_entry_count"] == 2
    assert issues[0].severity == "high"
