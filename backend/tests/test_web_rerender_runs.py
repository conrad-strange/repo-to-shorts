import json
from pathlib import Path

from gva.config import Settings
from gva.models.render import WorkflowResult
from gva.models.storyboard import Scene, Storyboard, VisualSpec
from gva.web import app as web_app


def test_web_rerender_creates_new_run_without_overwriting_source(tmp_path, monkeypatch) -> None:
    project_root = tmp_path / "demo"
    source_run = project_root / "runs" / "0001"
    source_run.mkdir(parents=True)
    (source_run / "workflow-metadata.json").write_text(
        json.dumps(
            {
                "run_id": "0001",
                "root_output_dir": str(project_root),
                "project_path": str(tmp_path / "repo"),
                "render_profile": "preview",
                "render_strategy": "remotion-primary",
                "video_mode": "short_30s",
            }
        ),
        encoding="utf-8",
    )
    (source_run / "project-insight.json").write_text("{}", encoding="utf-8")
    (source_run / "video-script.json").write_text("{}", encoding="utf-8")
    (source_run / "script.md").write_text("# script", encoding="utf-8")
    (source_run / "video.mp4").write_bytes(b"old-video")

    storyboard = Storyboard(
        title="Demo",
        aspect_ratio="9:16",
        fps=30,
        width=1080,
        height=1920,
        scenes=[
            Scene(
                id="scene-1",
                type="code",
                start=0,
                duration=3,
                narration="Demo narration",
                visual=VisualSpec(layout="code", headline="Code", code="print('hello world')"),
            )
        ],
    )
    (source_run / "storyboard.json").write_text(storyboard.model_dump_json(indent=2), encoding="utf-8")

    monkeypatch.setattr(web_app, "Settings", lambda: Settings(outputs_dir=tmp_path))

    def fake_workflow(**kwargs):
        run_id = kwargs["run_id"]
        output_dir = Path(kwargs["output_dir"]) / "runs" / run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "run_id": run_id,
            "root_output_dir": str(kwargs["output_dir"]),
            "video_path": str(output_dir / "video.mp4"),
        }
        (output_dir / "workflow-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (output_dir / "video.mp4").write_bytes(b"new-video")
        return WorkflowResult(output_dir=output_dir, metadata=metadata)

    monkeypatch.setattr(web_app, "run_render_workflow", fake_workflow)

    payload = web_app._rerender_payload(
        "demo",
        "0001",
        web_app.RerenderRequest(render_profile="preview", storyboard=storyboard.model_dump(mode="json")),
    )

    assert payload["run_id"] == "0002"
    assert (source_run / "video.mp4").read_bytes() == b"old-video"
    assert (project_root / "runs" / "0002" / "video.mp4").read_bytes() == b"new-video"
