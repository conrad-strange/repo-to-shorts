import json
from pathlib import Path

from gva.config import Settings
from gva.models.render import WorkflowResult
from gva.web import app as web_app


def test_github_slug_uses_owner_and_repo() -> None:
    assert web_app._slug_from_source("https://github.com/conrad-strange/repo-to-shorts") == "conrad-strange-repo-to-shorts"
    assert web_app._slug_from_source("https://github.com/conrad-strange/repo-to-shorts.git") == "conrad-strange-repo-to-shorts"


def test_workflow_request_passes_user_brief_and_auto_output_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(web_app, "Settings", lambda: Settings(outputs_dir=tmp_path))
    captured = {}

    def fake_workflow(**kwargs):
        captured.update(kwargs)
        output_dir = Path(kwargs["output_dir"]) / "runs" / "0001"
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "run_id": "0001",
            "root_output_dir": str(kwargs["output_dir"]),
            "user_brief": kwargs.get("user_brief"),
        }
        (output_dir / "workflow-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        return WorkflowResult(output_dir=output_dir, metadata=metadata)

    monkeypatch.setattr(web_app, "run_render_workflow", fake_workflow)

    payload = web_app._run_workflow_payload(
        web_app.WorkflowRequest(
            repo_url="https://github.com/conrad-strange/repo-to-shorts",
            user_brief="更偏真实使用体验，少讲技术栈",
            dry_run=True,
        )
    )

    assert Path(captured["output_dir"]).name == "conrad-strange-repo-to-shorts"
    assert captured["user_brief"] == "更偏真实使用体验，少讲技术栈"
    assert payload["metadata"]["user_brief"] == "更偏真实使用体验，少讲技术栈"
