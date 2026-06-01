from gva.agents.evaluator import render_evaluation_markdown
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
