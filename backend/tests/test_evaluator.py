from gva.agents.evaluator import _is_vertical_9_16, _parse_video_resolution, render_evaluation_markdown
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
